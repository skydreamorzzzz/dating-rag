#!/usr/bin/env python3
"""Inspect chunk JSONL quality before embedding/indexing."""

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.config import CHUNKS_DIR

REQUIRED_FIELDS = ("chunk_id", "text", "source_file", "document_id")


def inspect_chunks(path: Path) -> tuple[dict, Counter]:
    stats = {
        "total": 0,
        "empty_text": 0,
        "missing_chunk_id": 0,
        "duplicate_chunk_id": 0,
        "duplicate_text": 0,
        "missing_required": {field: 0 for field in REQUIRED_FIELDS},
        "length_min": 0,
        "length_max": 0,
        "length_avg": 0,
        "length_median": 0,
    }
    chunk_ids: Counter[str] = Counter()
    texts: Counter[str] = Counter()
    by_source: Counter[str] = Counter()
    lengths: list[int] = []

    with Path(path).open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            stats["total"] += 1

            text = record.get("text")
            clean_text = text.strip() if isinstance(text, str) else ""
            if not clean_text:
                stats["empty_text"] += 1
            else:
                texts[clean_text] += 1
                lengths.append(len(clean_text))

            chunk_id = record.get("chunk_id")
            if chunk_id:
                chunk_ids[str(chunk_id)] += 1
            else:
                stats["missing_chunk_id"] += 1

            for field in REQUIRED_FIELDS:
                value = record.get(field)
                if value is None or value == "":
                    stats["missing_required"][field] += 1

            by_source[str(record.get("source_file") or "<missing>")] += 1

    stats["duplicate_chunk_id"] = sum(count - 1 for count in chunk_ids.values() if count > 1)
    stats["duplicate_text"] = sum(count - 1 for count in texts.values() if count > 1)
    if lengths:
        stats["length_min"] = min(lengths)
        stats["length_max"] = max(lengths)
        stats["length_avg"] = round(sum(lengths) / len(lengths), 2)
        stats["length_median"] = statistics.median(lengths)
    return stats, by_source


def has_serious_issues(stats: dict) -> bool:
    return (
        stats["empty_text"] > 0
        or stats["missing_chunk_id"] > 0
        or stats["duplicate_chunk_id"] > 0
        or any(stats["missing_required"].values())
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect data/chunks/chunks.jsonl quality.")
    parser.add_argument("--path", type=Path, default=CHUNKS_DIR / "chunks.jsonl")
    parser.add_argument("--top-sources", type=int, default=20)
    args = parser.parse_args()

    stats, by_source = inspect_chunks(args.path)
    print("=== Chunk Quality Summary ===")
    print(f"  Total chunks             : {stats['total']}")
    print(f"  Empty text               : {stats['empty_text']}")
    print(f"  Missing chunk_id         : {stats['missing_chunk_id']}")
    print(f"  Duplicate chunk_id       : {stats['duplicate_chunk_id']}")
    print(f"  Duplicate exact text     : {stats['duplicate_text']}")
    print(f"  Text length min          : {stats['length_min']}")
    print(f"  Text length max          : {stats['length_max']}")
    print(f"  Text length avg          : {stats['length_avg']}")
    print(f"  Text length median       : {stats['length_median']}")
    print("  Missing required fields  :")
    for field, count in stats["missing_required"].items():
        print(f"    {field:<20}: {count}")

    print("\n=== Chunks By Source ===")
    for source_file, count in by_source.most_common(args.top_sources):
        print(f"  {count:>6}  {source_file}")

    if has_serious_issues(stats):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
