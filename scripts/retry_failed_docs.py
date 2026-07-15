#!/usr/bin/env python3
"""Retry DOC files currently represented in processed/failed.

This script is intentionally narrow: it only looks for failed records whose
source file is a .doc, then reruns the normal ingestion path for those original
raw files. It is useful after installing or fixing LibreOffice.
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.pipeline import _load_error_document, _split_and_write, ingest_file
from src.utils.config import FAILED_DIR, SUCCESS_DIR


def failed_doc_paths(failed_dir: Path) -> list[Path]:
    """Return unique original .doc paths found in failed JSONL records."""
    paths: dict[str, Path] = {}
    for jsonl_path in sorted(failed_dir.glob("*.jsonl")):
        with jsonl_path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                source_file = str(record.get("source_file") or "")
                source_path = str(record.get("source_path") or "")
                if source_file.lower().endswith(".doc") or source_path.lower().endswith(".doc"):
                    path = Path(source_path) if source_path else PROJECT_ROOT / "data" / "raw" / source_file
                    paths[str(path)] = path
                    break
    return sorted(paths.values(), key=lambda p: p.name)


def retry_doc(
    file_path: Path,
    success_dir: Path,
    failed_dir: Path,
) -> dict:
    """Retry a single DOC file and refresh stale counterpart output."""
    try:
        docs = ingest_file(file_path)
    except Exception as e:
        docs = [_load_error_document(file_path, e)]

    stats = _split_and_write(docs, file_path.stem, success_dir, failed_dir)

    success_output = success_dir / f"{file_path.stem}.jsonl"
    failed_output = failed_dir / f"{file_path.stem}.jsonl"
    if stats["success"] > 0 and stats["failed"] == 0 and failed_output.exists():
        failed_output.unlink()
    elif stats["failed"] > 0 and stats["success"] == 0 and success_output.exists():
        success_output.unlink()

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Retry .doc files currently found in data/processed/failed/.",
    )
    parser.add_argument("--failed-dir", type=Path, default=FAILED_DIR)
    parser.add_argument("--success-dir", type=Path, default=SUCCESS_DIR)
    parser.add_argument("--limit", type=int, default=None, help="Only retry the first N files.")
    parser.add_argument("--dry-run", action="store_true", help="List files without processing them.")
    args = parser.parse_args()

    docs = failed_doc_paths(args.failed_dir)
    if args.limit is not None:
        docs = docs[: args.limit]

    print(f"Found {len(docs)} failed .doc files")
    for file_path in docs:
        print(file_path)
        if args.dry_run:
            continue
        stats = retry_doc(file_path, args.success_dir, args.failed_dir)
        print(
            f"  total={stats['total']} success={stats['success']} "
            f"failed={stats['failed']} warnings={stats['has_warnings']}"
        )


if __name__ == "__main__":
    main()
