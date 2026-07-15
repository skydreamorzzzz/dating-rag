"""Chroma vector-store helpers for chunk retrieval."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.utils.config import DEFAULT_CHROMA_COLLECTION, VECTOR_STORE_DIR

CHROMA_METADATA_KEYS = (
    "document_id",
    "source_file",
    "file_type",
    "chunk_index",
    "page",
    "title",
    "section",
)


def read_chunks(path: Path) -> list[dict]:
    """Read chunk JSONL records from disk."""
    chunks: list[dict] = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"{path}:{line_no} is not valid JSON") from e
            validate_chunk(chunk, line_no)
            chunks.append(chunk)
    return chunks


def validate_chunk(chunk: dict, line_no: int | None = None) -> None:
    """Validate fields required for vector indexing."""
    label = f"line {line_no}: " if line_no is not None else ""
    if not chunk.get("chunk_id"):
        raise ValueError(f"{label}missing chunk_id")
    text = chunk.get("text")
    if not isinstance(text, str) or not text.strip():
        raise ValueError(f"{label}missing text")


def safe_metadata(chunk: dict) -> dict:
    """Return Chroma-safe metadata, filtering nulls and serializing complex values."""
    metadata: dict[str, str | int | float | bool] = {}
    for key in CHROMA_METADATA_KEYS:
        value = chunk.get(key)
        if value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            metadata[key] = value
        else:
            metadata[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)

    original_metadata = chunk.get("metadata")
    if original_metadata:
        metadata["original_metadata"] = json.dumps(
            original_metadata,
            ensure_ascii=False,
            sort_keys=True,
        )
    return metadata


class ChromaVectorStore:
    """Persistent Chroma collection wrapper."""

    def __init__(
        self,
        persist_dir: Path = VECTOR_STORE_DIR,
        collection_name: str = DEFAULT_CHROMA_COLLECTION,
    ) -> None:
        self.persist_dir = Path(persist_dir)
        self.collection_name = collection_name
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        try:
            import chromadb
        except ImportError as e:
            raise RuntimeError(
                "chromadb is required for vector indexing. Install requirements.txt first."
            ) from e
        self.client = chromadb.PersistentClient(path=str(self.persist_dir))

    def reset_collection(self):
        """Delete and recreate the configured collection."""
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        return self.get_collection()

    def get_collection(self):
        """Return the configured cosine-distance collection."""
        return self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_chunks(
        self,
        chunks: list[dict],
        embeddings: list[list[float]],
    ) -> int:
        """Upsert chunk records and embeddings into Chroma."""
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings length mismatch")
        if not chunks:
            return 0

        collection = self.get_collection()
        collection.upsert(
            ids=[chunk["chunk_id"] for chunk in chunks],
            embeddings=embeddings,
            documents=[chunk["text"] for chunk in chunks],
            metadatas=[safe_metadata(chunk) for chunk in chunks],
        )
        return len(chunks)

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[dict]:
        """Return retrieved chunks with text, metadata, id, and distance."""
        collection = self.get_collection()
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        ids = result.get("ids", [[]])[0]
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        return [
            {
                "chunk_id": chunk_id,
                "text": document,
                "metadata": metadata,
                "distance": distance,
            }
            for chunk_id, document, metadata, distance in zip(ids, documents, metadatas, distances)
        ]
