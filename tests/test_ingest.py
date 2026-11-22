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


def test_chunks_never_start_or_end_mid_word():
    words = [f"word{i:04d}" for i in range(600)]
    # mix of normal sentences and one very long sentence with no punctuation
    text = ". ".join(" ".join(words[i:i + 12]) for i in range(0, 300, 12)) + ". " + " ".join(words[300:])
    vocab = set(words)
    for c in chunk_page(make_page(text), chunk_size=200, overlap=60):
        first, last = c.text.split()[0], c.text.split()[-1].rstrip(".")
        assert first in vocab, f"chunk starts mid-word: {c.text[:30]!r}"
        assert last in vocab, f"chunk ends mid-word: {c.text[-30:]!r}"


def test_repeated_headers_and_page_numbers_are_removed():
    from regq.ingest.loader import remove_repeated_lines
    topics = ["sanctions", "bribery", "fraud", "PEPs", "CDD", "EDD", "SARs",
              "tipping off", "record keeping", "training"]
    bodies = [f"Guidance on {t}.\nFirms must assess {t} risk.\nSee the {t} annex.\nMore on {t}."
              for i, t in enumerate(topics, start=1)]
    pages = [f"FCG Financial Crime Guide\nwww.handbook.fca.org.uk May 2026\n{b}\nPage {i} of 10"
             for i, b in enumerate(bodies, start=1)]
    cleaned, removed = remove_repeated_lines(pages)
    assert len(removed) == 3
    assert cleaned == bodies


def test_repeated_body_text_in_middle_of_page_is_kept():
    from regq.ingest.loader import remove_repeated_lines
    middle = "\n".join(f"unique line {c}" for c in "abcdefgh")
    pages = [f"top {w}\n{middle}\nTable 1: risk factors\n{middle}\nbottom {w}"
             for w in ["one", "two", "three", "four", "five"]]
    cleaned, _ = remove_repeated_lines(pages)
    assert all("Table 1: risk factors" in t for t in cleaned)


def test_short_documents_keep_all_lines():
    from regq.ingest.loader import remove_repeated_lines
    pages = ["Title\nA", "Title\nB"]
    assert remove_repeated_lines(pages)[0] == pages


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
