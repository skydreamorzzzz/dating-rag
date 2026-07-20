#!/usr/bin/env python3
"""Build a persistent Chroma index from chunk JSONL."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.indexing.embeddings import SentenceTransformerEmbedder
from src.indexing.vector_store import ChromaVectorStore, read_chunks_lenient
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
    chunks, load_errors = read_chunks_lenient(chunks_path)
    embedder = SentenceTransformerEmbedder(
        model_name=model_name,
        batch_size=batch_size,
        normalize_embeddings=normalize_embeddings,
    )
    store = ChromaVectorStore(persist_dir=persist_dir, collection_name=collection_name)
    if rebuild:
        store.reset_collection()

    stats = {
        "chunks": len(chunks),
        "success": 0,
        "failed": load_errors,
        "skipped": 0,
        "total_vectors": 0,
    }
    unique_chunks: list[dict] = []
    seen_ids: set[str] = set()
    for chunk in chunks:
        chunk_id = chunk["chunk_id"]
        if chunk_id in seen_ids:
            stats["skipped"] += 1
            continue
        seen_ids.add(chunk_id)
        unique_chunks.append(chunk)

    if not rebuild:
        existing_ids = store.existing_ids(chunk["chunk_id"] for chunk in unique_chunks)
        if existing_ids:
            stats["skipped"] += len(existing_ids)
            unique_chunks = [
                chunk for chunk in unique_chunks
                if chunk["chunk_id"] not in existing_ids
            ]

    for batch in batched(unique_chunks, batch_size):
        try:
            texts = [chunk["text"] for chunk in batch]
            embeddings = embedder.encode_documents(texts)
            stats["success"] += store.upsert_chunks(batch, embeddings)
        except Exception:
            for chunk in batch:
                try:
                    embedding = embedder.encode_documents([chunk["text"]])[0]
                    stats["success"] += store.upsert_chunks([chunk], [embedding])
                except Exception:
                    stats["failed"] += 1

    stats["total_vectors"] = store.count()
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Chroma vector index from chunks.")
    parser.add_argument("--chunks", type=Path, default=CHUNKS_DIR)
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
    print(f"  Success         : {stats['success']}")
    print(f"  Failed          : {stats['failed']}")
    print(f"  Skipped         : {stats['skipped']}")
    print(f"  Total vectors   : {stats['total_vectors']}")
    print(f"  Persist dir     : {args.persist_dir}")
    print(f"  Collection      : {args.collection}")


if __name__ == "__main__":
    main()
