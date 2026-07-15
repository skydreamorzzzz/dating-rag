#!/usr/bin/env python3
"""CLI entry point: re-validate existing JSONL files and split into success/ and failed/.

Prefer running ``ingest.py`` directly — it validates inline during ingestion.
Use this script only when you need to re-validate already-extracted data.
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.preprocessing.validator import validate_file, validate_directory
from src.utils.config import SUCCESS_DIR, FAILED_DIR
from src.utils.logger import get_logger


def main():
    parser = argparse.ArgumentParser(
        description="Re-validate existing JSONL files and split into success/ and failed/.",
    )
    parser.add_argument(
        "path", type=Path,
        help="Single .jsonl file or directory of .jsonl files to validate",
    )
    parser.add_argument(
        "--success-dir", type=Path, default=None,
        help="Output directory for passing records (default: data/processed/success/)",
    )
    parser.add_argument(
        "--failed-dir", type=Path, default=None,
        help="Output directory for failing records (default: data/processed/failed/)",
    )
    args = parser.parse_args()

    logger = get_logger("validate")
    success_dir = args.success_dir or SUCCESS_DIR
    failed_dir = args.failed_dir or FAILED_DIR

    if args.path.is_file():
        if args.path.suffix.lower() != ".jsonl":
            parser.error(f"Expected .jsonl file, got: {args.path}")
        stats = validate_file(args.path, success_dir, failed_dir)
    elif args.path.is_dir():
        stats = validate_directory(args.path, success_dir, failed_dir)
    else:
        parser.error(f"Path not found: {args.path}")

    if stats:
        print("\n=== Validation Summary ===")
        print(f"  Files processed : {stats.get('files', 1)}")
        print(f"  Total records   : {stats['total']}")
        print(f"  Success         : {stats['success']}")
        print(f"  Failed          : {stats['failed']}")
        print(f"  - empty_text    : {stats['empty_text']}")
        print(f"  - has_warnings  : {stats['has_warnings']}")
        print(f"  - needs_ocr     : {stats['needs_ocr']}")
        print(f"  - parse_errors  : {stats['parse_errors']}")
        print(f"\n  Success dir     : {success_dir}")
        print(f"  Failed dir      : {failed_dir}")


if __name__ == "__main__":
    main()
