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


def load_pdf(path: str | Path) -> list[Page]:
    path = Path(path)
    reader = PdfReader(str(path))
    pages: list[Page] = []
    for i, pdf_page in enumerate(reader.pages, start=1):
        try:
            text = clean_text(pdf_page.extract_text() or "")
        except Exception as exc:  # a single bad page shouldn't stop ingestion
            log.warning("Could not read %s page %d: %s", path.name, i, exc)
            continue
        if text:
            pages.append(Page(source=path.name, page=i, text=text))
    if not pages:
        log.warning("%s has no extractable text (scanned PDF? needs OCR)", path.name)
    return pages


def load_directory(directory: str | Path) -> Iterator[tuple[Path, list[Page]]]:
    for pdf in sorted(Path(directory).glob("*.pdf")):
        yield pdf, load_pdf(pdf)
