# RegQ — Trustworthy AI Q&A over Financial Regulations

Ask questions about public AML / KYC / fraud regulations and get answers **with exact citations** —
or an honest *"not covered in the documents"*. Ships with a reproducible **evaluation report**.

> Status: 🚧 Week 1 — project skeleton

## Why
Compliance teams spend hours searching regulations, and generic chatbots hallucinate.
RegQ answers only from source documents, cites every claim, refuses out-of-scope questions,
and measures its own accuracy.

## Architecture
```
PDFs → Parse & chunk → Embed → Vector DB
                                   ↓
Question → Guardrails → Hybrid search (vector + BM25) → Re-rank
                                   ↓
              LLM answers ONLY from retrieved text + citations
                                   ↓
            Answer + sources   (or "Not covered in documents")
```

## Project layout
| Path | Purpose |
|---|---|
| `config/settings.yaml` | Models, chunk sizes, retrieval settings |
| `data/sources.md` | List of public documents used (with links) |
| `data/raw/` | Downloaded PDFs (not committed) |
| `data/processed/` | Parsed chunks (not committed) |
| `src/regq/ingest/` | `loader.py` — read PDFs · `chunker.py` — split into chunks with page/section metadata |
| `src/regq/index/` | `embedder.py` — create embeddings · `vector_store.py` — Chroma / pgvector wrapper |
| `src/regq/retrieval/` | `hybrid_search.py` — vector + BM25 · `reranker.py` — re-rank top results |
| `src/regq/generation/` | `prompts.py` — system prompt & citation format · `answer.py` — call LLM, build answer |
| `src/regq/guardrails/` | `injection.py` — prompt-injection checks · `pii.py` — redact PII from questions |
| `src/regq/api/main.py` | FastAPI endpoint `/ask` |
| `app/streamlit_app.py` | Simple chat UI |
| `scripts/ingest.py` | One command to ingest all documents |
| `eval/golden_set.jsonl` | Test questions with expected answers & sources |
| `eval/run_eval.py` | Runs evaluation, writes results to `eval/reports/` |
| `tests/` | Unit tests |
| `docs/` | Architecture notes & design decisions |

## Quick start
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add your API key
python scripts/ingest.py      # week 1
streamlit run app/streamlit_app.py   # week 2
```

## Evaluation
See `eval/reports/` (coming in week 5).

## Roadmap
- [ ] Week 1 — Ingest & index documents
- [ ] Week 2 — Q&A with citations + Streamlit UI
- [ ] Week 3 — Hybrid search, refusals, guardrails
- [ ] Week 4 — 50-question golden test set
- [ ] Week 5 — Evaluation runs & report
- [ ] Week 6 — Docker, demo video, write-up

## Disclaimer
Uses only publicly available regulatory documents. Not legal or compliance advice.
