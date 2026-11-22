# Design decisions

Record each key choice as you go — this becomes great material for the write-up and interviews.

| Date | Decision | Options considered | Why |
|---|---|---|---|
| | Vector store: Chroma (local) | Chroma, pgvector, FAISS | Zero setup for week 1; switch to pgvector later |
| | Embeddings: bge-small (local) | bge, Voyage, OpenAI | Free, good quality, no extra API key |
