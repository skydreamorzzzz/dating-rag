#!/usr/bin/env python3
"""CLI entry point: build text chunks from validated success records."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.preprocessing.chunker import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    build_chunks_from_success,
)
from src.utils.config import CHUNKS_DIR, SUCCESS_DIR


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build chunk JSONL from data/processed/success/ records.",
    )
    parser.add_argument("--input-dir", type=Path, default=SUCCESS_DIR)
    parser.add_argument("--output", type=Path, default=CHUNKS_DIR / "chunks.jsonl")
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--chunk-overlap", type=int, default=DEFAULT_CHUNK_OVERLAP)
    args = parser.parse_args()

    stats = build_chunks_from_success(
        success_dir=args.input_dir,
        output_path=args.output,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )

    print("\n=== Chunk Build Summary ===")
    print(f"  Total records  : {stats['records']}")
    print(f"  Documents read : {stats['documents']}")
    print(f"  Chunks written : {stats['chunks']}")
    print(f"  Skipped records: {stats['skipped']}")
    print(f"  Errors         : {stats['errors']}")
    print(f"  Output         : {args.output}")


if __name__ == "__main__":
    main()
