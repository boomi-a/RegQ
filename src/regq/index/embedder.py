"""Turn text into vectors with a local sentence-transformers model (no API key needed)."""
from __future__ import annotations

from functools import cached_property


class Embedder:
    # bge models work best with this prefix on *queries* (not on documents)
    QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

    def __init__(self, model_name: str = "BAAI/bge-small-en-v1.5", batch_size: int = 32):
        self.model_name = model_name
        self.batch_size = batch_size

    @cached_property
    def model(self):
        from sentence_transformers import SentenceTransformer  # heavy import, load lazily
        return SentenceTransformer(self.model_name)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(texts, batch_size=self.batch_size,
                                    normalize_embeddings=True, show_progress_bar=len(texts) > 100)
        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        prefix = self.QUERY_PREFIX if "bge" in self.model_name.lower() else ""
        return self.model.encode(prefix + text, normalize_embeddings=True).tolist()
