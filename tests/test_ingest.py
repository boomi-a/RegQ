import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from regq.ingest.chunker import chunk_page  # noqa: E402
from regq.ingest.loader import Page, clean_text, load_pdf  # noqa: E402


def make_page(text: str) -> Page:
    return Page(source="doc.pdf", page=3, text=text)


def test_clean_text_fixes_hyphenation_and_spaces():
    assert clean_text("regu-\nlation   applies") == "regulation applies"


def test_chunks_respect_size_and_keep_metadata():
    text = " ".join(f"Sentence number {i} about customer due diligence." for i in range(200))
    chunks = chunk_page(make_page(text), chunk_size=300, overlap=50)
    assert len(chunks) > 1
    assert all(len(c.text) <= 300 for c in chunks)
    assert all(c.source == "doc.pdf" and c.page == 3 for c in chunks)
    assert len({c.id for c in chunks}) == len(chunks)


def test_chunks_overlap():
    text = " ".join(f"Rule {i} requires enhanced checks." for i in range(100))
    a, b = chunk_page(make_page(text), chunk_size=200, overlap=60)[:2]
    assert a.text[-30:] in b.text


def test_very_long_word_is_hard_split():
    chunks = chunk_page(make_page("x" * 1000), chunk_size=300, overlap=50)
    assert all(len(c.text) <= 300 for c in chunks)
    assert "".join(c.text for c in chunks).count("x") >= 1000


def test_short_page_gives_one_chunk():
    chunks = chunk_page(make_page("Short page."), chunk_size=800, overlap=150)
    assert [c.text for c in chunks] == ["Short page."]


def test_overlap_must_be_smaller_than_size():
    with pytest.raises(ValueError):
        chunk_page(make_page("text"), chunk_size=100, overlap=100)


def test_html_saved_as_pdf_is_skipped(tmp_path):
    fake = tmp_path / "fake.pdf"
    fake.write_text("<!DOCTYPE html><html>Access denied</html>")
    assert load_pdf(fake) == []


def test_load_pdf_reads_pages(tmp_path):
    reportlab = pytest.importorskip("reportlab.pdfgen.canvas")
    pdf = tmp_path / "sample.pdf"
    c = reportlab.Canvas(str(pdf))
    c.drawString(72, 720, "Page one: customer due diligence.")
    c.showPage()
    c.drawString(72, 720, "Page two: politically exposed persons.")
    c.save()
    pages = load_pdf(pdf)
    assert [p.page for p in pages] == [1, 2]
    assert "politically exposed" in pages[1].text
