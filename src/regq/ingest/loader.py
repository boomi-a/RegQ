"""Read PDFs page by page, keeping source and page number for citations."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from pypdf import PdfReader

log = logging.getLogger(__name__)


@dataclass
class Page:
    source: str      # file name, e.g. "fatf_recommendations.pdf"
    page: int        # 1-based page number
    text: str


def clean_text(text: str) -> str:
    """Normalise whitespace and fix words hyphenated across line breaks."""
    text = text.replace("\x00", "")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)    # "regu-\nlation" -> "regulation"
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def is_real_pdf(path: Path) -> bool:
    """A download that failed often saves an HTML error page with a .pdf name."""
    with open(path, "rb") as f:
        return f.read(1024).lstrip().startswith(b"%PDF")


def load_pdf(path: str | Path) -> list[Page]:
    path = Path(path)
    if not is_real_pdf(path):
        log.error("SKIPPED %s — not a real PDF (probably a web page saved by a failed "
                  "download). Re-download it from the link in data/sources.md.", path.name)
        return []
    try:
        reader = PdfReader(str(path))
    except Exception as exc:
        log.error("SKIPPED %s — could not open PDF: %s", path.name, exc)
        return []
    raw: list[tuple[int, str]] = []
    for i, pdf_page in enumerate(reader.pages, start=1):
        try:
            raw.append((i, pdf_page.extract_text() or ""))
        except Exception as exc:  # a single bad page shouldn't stop ingestion
            log.warning("Could not read %s page %d: %s", path.name, i, exc)

    texts, removed = remove_repeated_lines([t for _, t in raw])
    if removed:
        log.info("%s: removed %d repeated header/footer line(s)", path.name, len(removed))

    pages = [Page(source=path.name, page=i, text=t)
             for (i, _), t in zip(raw, map(clean_text, texts)) if t]
    if not pages:
        log.warning("%s has no extractable text (scanned PDF? needs OCR)", path.name)
    return pages


def _line_key(line: str) -> str:
    """Normalise a line so 'Page 3 of 40' and 'Page 4 of 40' compare equal."""
    return re.sub(r"\d+", "#", re.sub(r"\s+", " ", line)).strip().lower()


def _edge_lines(text: str, top: int, bottom: int) -> list[tuple[int, str]]:
    lines = text.splitlines()
    idx = sorted(set(range(min(top, len(lines)))) |
                 set(range(max(len(lines) - bottom, 0), len(lines))))
    return [(i, lines[i]) for i in idx]


def remove_repeated_lines(page_texts: list[str], min_share: float = 0.5, min_pages: int = 4,
                          max_len: int = 150, top: int = 4, bottom: int = 3
                          ) -> tuple[list[str], set[str]]:
    """Drop headers/footers: short lines near the top or bottom of a page that repeat on
    at least `min_share` of pages (page numbers allowed to differ). Body text is never
    touched. Returns the cleaned texts and the removed line keys."""
    if len(page_texts) < min_pages:
        return page_texts, set()

    seen_on: dict[str, int] = {}
    for text in page_texts:
        for key in {_line_key(l) for _, l in _edge_lines(text, top, bottom)}:
            if key and len(key) <= max_len:
                seen_on[key] = seen_on.get(key, 0) + 1

    threshold = max(3, int(len(page_texts) * min_share))
    repeated = {k for k, n in seen_on.items() if n >= threshold}
    if not repeated:
        return page_texts, set()

    cleaned = []
    for text in page_texts:
        lines = text.splitlines()
        drop = {i for i, l in _edge_lines(text, top, bottom) if _line_key(l) in repeated}
        cleaned.append("\n".join(l for i, l in enumerate(lines) if i not in drop))
    return cleaned, repeated


def load_directory(directory: str | Path) -> Iterator[tuple[Path, list[Page]]]:
    for pdf in sorted(Path(directory).glob("*.pdf")):
        yield pdf, load_pdf(pdf)
