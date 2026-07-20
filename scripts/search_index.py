#!/usr/bin/env python3
"""Search the persistent Chroma index and print top matching chunks."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.indexing.embeddings import SentenceTransformerEmbedder
from src.indexing.vector_store import ChromaVectorStore
from src.utils.config import (
    DEFAULT_CHROMA_COLLECTION,
    DEFAULT_EMBEDDING_BATCH_SIZE,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_NORMALIZE_EMBEDDINGS,
    VECTOR_STORE_DIR,
)


def search_index(
    question: str,
    persist_dir: Path = VECTOR_STORE_DIR,
    collection_name: str = DEFAULT_CHROMA_COLLECTION,
    model_name: str = DEFAULT_EMBEDDING_MODEL,
    batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
    top_k: int = 5,
    normalize_embeddings: bool = DEFAULT_NORMALIZE_EMBEDDINGS,
) -> list[dict]:
    """Embed a query and return top-k vector search results."""
    embedder = SentenceTransformerEmbedder(
        model_name=model_name,
        batch_size=batch_size,
        normalize_embeddings=normalize_embeddings,
    )
    store = ChromaVectorStore(persist_dir=persist_dir, collection_name=collection_name)
    return store.query(embedder.encode_query(question), top_k=top_k)


def main() -> None:
    parser = argparse.ArgumentParser(description="Search the Chroma chunk index.")
    parser.add_argument("question", nargs="?", help="Question to search for.")
    parser.add_argument("--persist-dir", type=Path, default=VECTOR_STORE_DIR)
    parser.add_argument("--collection", default=DEFAULT_CHROMA_COLLECTION)
    parser.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_EMBEDDING_BATCH_SIZE)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--no-normalize", action="store_true")
    args = parser.parse_args()

    question = args.question or input("Question: ").strip()
    results = search_index(
        question=question,
        persist_dir=args.persist_dir,
        collection_name=args.collection,
        model_name=args.model,
        batch_size=args.batch_size,
        top_k=args.top_k,
        normalize_embeddings=not args.no_normalize and DEFAULT_NORMALIZE_EMBEDDINGS,
    )

    for rank, result in enumerate(results, start=1):
        metadata = result.get("metadata") or {}
        source_file = metadata.get("source_file", "")
        page = metadata.get("page", "")
        section = metadata.get("section", "")
        location = f"{source_file}"
        if page != "":
            location += f" page={page}"
        if section:
            location += f" section={section}"
        print(f"\n[{rank}] chunk_id={result['chunk_id']} distance={result['distance']:.4f}")
        print(f"source: {location}")
        print(result["text"])


if __name__ == "__main__":
    main()
