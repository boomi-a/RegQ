"""Split pages into overlapping chunks that keep their source and page number."""
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


def _split_units(text: str) -> list[str]:
    """Split into paragraphs, then sentences for very long paragraphs."""
    units: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        para = para.strip()
        if not para:
            continue
        units.extend(s.strip() for s in re.split(r"(?<=[.;:])\s+", para) if s.strip())
    return units


def _make_id(source: str, page: int, idx: int, text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return f"{source}::p{page}::c{idx}::{digest}"


def chunk_page(page: Page, chunk_size: int = 800, overlap: int = 150) -> list[Chunk]:
    """Greedy packing of sentences up to chunk_size chars, carrying ~overlap chars forward."""
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks: list[Chunk] = []
    current = ""

    def flush(text: str) -> None:
        idx = len(chunks)
        chunks.append(Chunk(_make_id(page.source, page.page, idx, text), text,
                            page.source, page.page, idx))

    for unit in _split_units(page.text):
        # hard-split any single unit longer than chunk_size
        while len(unit) > chunk_size:
            if current:
                flush(current)
                current = current[-overlap:] if overlap else ""
            room = chunk_size - len(current) - (1 if current else 0)
            piece, unit = unit[:room], unit[room:]
            current = f"{current} {piece}".strip()
            flush(current)
            current = current[-overlap:] if overlap else ""

        candidate = f"{current} {unit}".strip()
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            flush(current)
            tail = current[-overlap:] if overlap else ""
            current = f"{tail} {unit}".strip()

    if current and (not chunks or current != chunks[-1].text[-len(current):]):
        flush(current)
    return chunks


def chunk_pages(pages: list[Page], chunk_size: int = 800, overlap: int = 150) -> list[Chunk]:
    out: list[Chunk] = []
    for p in pages:
        out.extend(chunk_page(p, chunk_size, overlap))
    return out
