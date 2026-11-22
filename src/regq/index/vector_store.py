"""Thin wrapper around a persistent Chroma collection (swap for pgvector later)."""
from __future__ import annotations

from pathlib import Path

from regq.ingest.chunker import Chunk


class VectorStore:
    def __init__(self, path: str | Path, collection: str = "regq"):
        import chromadb  # imported here so the rest of the package works without it

        self.client = chromadb.PersistentClient(path=str(path))
        self.collection = self.client.get_or_create_collection(
            name=collection, metadata={"hnsw:space": "cosine"}
        )

    def upsert(self, chunks: list[Chunk], embeddings: list[list[float]], batch: int = 500) -> None:
        for i in range(0, len(chunks), batch):
            part = chunks[i:i + batch]
            self.collection.upsert(
                ids=[c.id for c in part],
                documents=[c.text for c in part],
                embeddings=embeddings[i:i + batch],
                metadatas=[{"source": c.source, "page": c.page, "chunk_index": c.chunk_index}
                           for c in part],
            )

    def query(self, embedding: list[float], top_k: int = 8) -> list[dict]:
        res = self.collection.query(query_embeddings=[embedding], n_results=top_k)
        return [
            {"id": i, "text": d, "score": 1 - dist, **m}
            for i, d, m, dist in zip(res["ids"][0], res["documents"][0],
                                     res["metadatas"][0], res["distances"][0])
        ]

    def delete_source(self, source: str) -> None:
        self.collection.delete(where={"source": source})

    def count(self) -> int:
        return self.collection.count()
