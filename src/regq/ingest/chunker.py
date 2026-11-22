"""Split pages into overlapping chunks that keep their source and page number.

Chunks are built from whole sentences. The overlap between consecutive chunks is
also made of whole sentences (or, failing that, whole words), so no chunk ever
starts or ends in the middle of a word.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass

from regq.ingest.loader import Page


@dataclass
class Chunk:
    id: str
    text: str
    source: str
    page: int
    chunk_index: int   # position within the page

    def to_dict(self) -> dict:
        return asdict(self)


def _split_units(text: str, max_len: int) -> list[str]:
    """Paragraphs -> sentences -> (if still too long) word-aligned pieces."""
    units: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = " ".join(para.split())          # flatten line breaks inside a paragraph
        if not para:
            continue
        for sent in re.split(r"(?<=[.;:?!])\s+", para):
            units.extend(_split_long(sent, max_len))
    return units


def _split_long(text: str, max_len: int) -> list[str]:
    """Split text longer than max_len at word boundaries (hard cut only for a giant word)."""
    pieces: list[str] = []
    while len(text) > max_len:
        cut = text.rfind(" ", 0, max_len + 1)
        if cut <= 0:                           # a single 'word' longer than max_len
            cut = max_len
        pieces.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        pieces.append(text)
    return pieces


def _word_tail(text: str, max_chars: int) -> str:
    """Last <= max_chars of text, starting at a word boundary."""
    if len(text) <= max_chars:
        return text
    tail = text[-max_chars:]
    space = tail.find(" ")
    return tail[space + 1:] if space != -1 else ""


def _overlap_units(units: list[str], overlap: int) -> list[str]:
    """Trailing whole sentences that fit in `overlap` chars; else a word-aligned tail."""
    carry: list[str] = []
    size = 0
    for u in reversed(units):
        extra = len(u) + (1 if carry else 0)
        if size + extra > overlap:
            break
        carry.insert(0, u)
        size += extra
    if carry:
        return carry
    tail = _word_tail(units[-1], overlap) if units and overlap else ""
    return [tail] if tail else []


def _make_id(source: str, page: int, idx: int, text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return f"{source}::p{page}::c{idx}::{digest}"


def chunk_page(page: Page, chunk_size: int = 800, overlap: int = 150) -> list[Chunk]:
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    units = _split_units(page.text, max_len=chunk_size - overlap - 1)
    chunks: list[Chunk] = []
    current: list[str] = []
    fresh = False            # does `current` contain anything beyond carried-over overlap?

    def length(parts: list[str]) -> int:
        return sum(len(p) for p in parts) + max(len(parts) - 1, 0)

    def flush() -> None:
        text = " ".join(current)
        idx = len(chunks)
        chunks.append(Chunk(_make_id(page.source, page.page, idx, text), text,
                            page.source, page.page, idx))

    for unit in units:
        if current and length(current + [unit]) > chunk_size:
            flush()
            current = _overlap_units(current, overlap)
            fresh = False
            if length(current + [unit]) > chunk_size:   # overlap + unit still too big
                current = []
        current.append(unit)
        fresh = True

    if current and fresh:
        flush()
    return chunks


def chunk_pages(pages: list[Page], chunk_size: int = 800, overlap: int = 150) -> list[Chunk]:
    out: list[Chunk] = []
    for p in pages:
        out.extend(chunk_page(p, chunk_size, overlap))
    return out
