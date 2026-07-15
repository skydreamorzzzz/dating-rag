#!/usr/bin/env python3
"""Build a persistent Chroma index from chunk JSONL."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.indexing.embeddings import SentenceTransformerEmbedder
from src.indexing.vector_store import ChromaVectorStore, read_chunks
from src.utils.config import (
    CHUNKS_DIR,
    DEFAULT_CHROMA_COLLECTION,
    DEFAULT_EMBEDDING_BATCH_SIZE,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_NORMALIZE_EMBEDDINGS,
    VECTOR_STORE_DIR,
)


def batched(items: list[dict], batch_size: int):
    for start in range(0, len(items), batch_size):
        yield items[start:start + batch_size]


def build_index(
    chunks_path: Path,
    persist_dir: Path,
    collection_name: str,
    model_name: str,
    batch_size: int,
    normalize_embeddings: bool,
    rebuild: bool,
) -> dict:
    chunks = read_chunks(chunks_path)
    embedder = SentenceTransformerEmbedder(
        model_name=model_name,
        batch_size=batch_size,
        normalize_embeddings=normalize_embeddings,
    )
    store = ChromaVectorStore(persist_dir=persist_dir, collection_name=collection_name)
    if rebuild:
        store.reset_collection()

    indexed = 0
    for batch in batched(chunks, batch_size):
        texts = [chunk["text"] for chunk in batch]
        embeddings = embedder.encode_documents(texts)
        indexed += store.upsert_chunks(batch, embeddings)

    return {"chunks": len(chunks), "indexed": indexed}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Chroma vector index from chunks.")
    parser.add_argument("--chunks", type=Path, default=CHUNKS_DIR / "chunks.jsonl")
    parser.add_argument("--persist-dir", type=Path, default=VECTOR_STORE_DIR)
    parser.add_argument("--collection", default=DEFAULT_CHROMA_COLLECTION)
    parser.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_EMBEDDING_BATCH_SIZE)
    parser.add_argument("--rebuild", action="store_true", help="Delete and rebuild collection first.")
    parser.add_argument(
        "--no-normalize",
        action="store_true",
        help="Disable embedding normalization.",
    )
    args = parser.parse_args()

    stats = build_index(
        chunks_path=args.chunks,
        persist_dir=args.persist_dir,
        collection_name=args.collection,
        model_name=args.model,
        batch_size=args.batch_size,
        normalize_embeddings=not args.no_normalize and DEFAULT_NORMALIZE_EMBEDDINGS,
        rebuild=args.rebuild,
    )

    print("\n=== Index Build Summary ===")
    print(f"  Chunks read     : {stats['chunks']}")
    print(f"  Vectors indexed : {stats['indexed']}")
    print(f"  Persist dir     : {args.persist_dir}")
    print(f"  Collection      : {args.collection}")


if __name__ == "__main__":
    main()
