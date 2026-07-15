"""Sentence-transformers embedding wrapper for retrieval indexing."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from src.utils.config import (
    DEFAULT_EMBEDDING_BATCH_SIZE,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_NORMALIZE_EMBEDDINGS,
    DEFAULT_QUERY_INSTRUCTION,
)


class SentenceTransformerEmbedder:
    """Batch embedding interface for BGE sentence-transformers models."""

    def __init__(
        self,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
        normalize_embeddings: bool = DEFAULT_NORMALIZE_EMBEDDINGS,
        device: str | None = None,
        query_instruction: str = DEFAULT_QUERY_INSTRUCTION,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        self.model_name = model_name
        self.batch_size = batch_size
        self.normalize_embeddings = normalize_embeddings
        self.device = device or _auto_device()
        self.query_instruction = query_instruction
        self._model: Any | None = None

    @property
    def model(self) -> Any:
        """Load the sentence-transformers model lazily."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as e:
                raise RuntimeError(
                    "sentence-transformers is required for embeddings. "
                    "Install requirements.txt first."
                ) from e
            self._model = SentenceTransformer(self.model_name, device=self.device)
        return self._model

    def encode_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Encode passage/chunk texts in batches."""
        return self._encode(list(texts))

    def encode_query(self, query: str) -> list[float]:
        """Encode one retrieval query with the BGE Chinese query instruction."""
        return self._encode([self._format_query(query)])[0]

    def _encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=self.normalize_embeddings,
            show_progress_bar=False,
        )
        if hasattr(embeddings, "tolist"):
            return embeddings.tolist()
        return [list(row) for row in embeddings]

    def _format_query(self, query: str) -> str:
        query = query.strip()
        if not self.query_instruction:
            return query
        if query.startswith(self.query_instruction):
            return query
        return f"{self.query_instruction}{query}"


def _auto_device() -> str:
    try:
        import torch
    except ImportError:
        return "cpu"
    return "cuda" if torch.cuda.is_available() else "cpu"
