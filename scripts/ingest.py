"""Ingest every PDF in data/raw/ into the vector store.

Usage:
    python scripts/ingest.py              # ingest all PDFs
    python scripts/ingest.py --dry-run    # parse + chunk only, no embeddings
    python scripts/ingest.py --query "What is customer due diligence?"   # quick sanity check
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys

# keep Hugging Face / transformers quiet (must be set before they are imported)
os.environ.setdefault("HF_HUB_VERBOSITY", "error")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from regq.ingest.chunker import chunk_pages  # noqa: E402
from regq.ingest.loader import load_directory  # noqa: E402
from regq.settings import PROCESSED_DIR, PROJECT_ROOT, RAW_DIR, load_settings  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("ingest")


class _OnlyOurLogs(logging.Filter):
    """Show INFO from this project; only ERROR+ from libraries (httpx, HF, torch...)."""
    def filter(self, record: logging.LogRecord) -> bool:
        ours = record.name == "ingest" or record.name.startswith("regq")
        return ours or record.levelno >= logging.ERROR


for _h in logging.getLogger().handlers:
    _h.addFilter(_OnlyOurLogs())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="parse and chunk only")
    ap.add_argument("--query", help="after ingesting, run one test search")
    args = ap.parse_args()

    cfg = load_settings()
    size, overlap = cfg["chunking"]["chunk_size"], cfg["chunking"]["chunk_overlap"]

    pdfs = sorted(RAW_DIR.glob("*.pdf"))
    if not pdfs:
        log.warning("No PDFs found in %s — download the documents listed in data/sources.md",
                    RAW_DIR.relative_to(PROJECT_ROOT))
        if not args.query:
            return 1

    t0 = time.time()
    all_chunks = []
    for pdf, pages in load_directory(RAW_DIR):
        chunks = chunk_pages(pages, size, overlap)
        log.info("%-40s %4d pages -> %5d chunks", pdf.name, len(pages), len(chunks))
        all_chunks.extend(chunks)

    # keep a plain copy of the chunks: used later for BM25 keyword search and debugging
    if all_chunks:
        PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
        out = PROCESSED_DIR / "chunks.jsonl"
        with open(out, "w", encoding="utf-8") as f:
            for c in all_chunks:
                f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")
        log.info("Wrote %d chunks to %s", len(all_chunks), out.relative_to(PROJECT_ROOT))

    if args.dry_run:
        log.info("Dry run — skipping embeddings. Done in %.1fs", time.time() - t0)
        return 0

    from regq.index.embedder import Embedder
    from regq.index.vector_store import VectorStore

    embedder = Embedder(cfg["embeddings"]["model"])
    store = VectorStore(PROJECT_ROOT / cfg["vector_store"]["path"])

    if all_chunks:
        # re-ingesting a file replaces its old chunks
        for source in {c.source for c in all_chunks}:
            store.delete_source(source)
        log.info("Embedding %d chunks with %s ...", len(all_chunks), embedder.model_name)
        vectors = embedder.embed_documents([c.text for c in all_chunks])
        store.upsert(all_chunks, vectors)
        log.info("Vector store now holds %d chunks. Done in %.1fs", store.count(), time.time() - t0)

    if args.query:
        if store.count() == 0:
            log.error("The vector store is empty — add PDFs to data/raw/ and run ingest first.")
            return 1
        hits =store.query(embedder.embed_query(args.query), top_k=cfg["retrieval"]["top_k"])
        print(f"\nTop results for: {args.query}\n")
        for h in hits[:5]:
            print(f"[{h['score']:.3f}] {h['source']} p.{h['page']}: {h['text'][:160]}...\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
