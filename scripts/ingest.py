#!/usr/bin/env python3
"""CLI entry point: ingest documents, validate, split into success/ and failed/."""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ingestion.pipeline import ingest_directory, ingest_file, _split_and_write
from src.utils.config import RAW_DIR, SUCCESS_DIR, FAILED_DIR
from src.utils.logger import get_logger


def main():
    parser = argparse.ArgumentParser(
        description="Ingest documents, validate, and split into success/ and failed/.",
    )
    parser.add_argument(
        "path", nargs="?", type=Path,
        help="Single file or directory to ingest (default: data/raw/)",
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

    logger = get_logger("ingest")
    success_dir = args.success_dir or SUCCESS_DIR
    failed_dir = args.failed_dir or FAILED_DIR

    if args.path is None:
        logger.info("No path given, ingesting entire data/raw/ directory")
        totals = ingest_directory(RAW_DIR, success_dir, failed_dir)
    elif args.path.is_dir():
        totals = ingest_directory(args.path, success_dir, failed_dir)
    elif args.path.is_file():
        docs = ingest_file(args.path)
        stem = args.path.stem
        totals = _split_and_write(docs, stem, success_dir, failed_dir)
        logger.info(
            "%s: %d records — success=%d failed=%d",
            args.path.name, totals["total"], totals["success"], totals["failed"],
        )
    else:
        parser.error(f"Path not found: {args.path}")

    if totals:
        print("\n=== Ingestion Summary ===")
        print(f"  Files processed : {totals.get('files', 1)}")
        print(f"  Total records   : {totals['total']}")
        print(f"  Success         : {totals['success']}")
        print(f"  Failed          : {totals['failed']}")
        print(f"  - empty_text    : {totals['empty_text']}")
        print(f"  - garbled_text  : {totals['garbled_text']}")
        print(f"  - has_warnings  : {totals['has_warnings']}")
        print(f"  - needs_ocr     : {totals['needs_ocr']}")
        skipped = totals.get('skipped_unsupported', 0)
        dupes = totals.get('skipped_duplicate', 0)
        errors = totals.get('load_errors', 0)
        if skipped or dupes or errors:
            print(f"  Skipped (unsupported): {skipped}")
            print(f"  Skipped (duplicates) : {dupes}")
            print(f"  Load errors          : {errors}")
        print(f"\n  Success dir     : {success_dir}")
        print(f"  Failed dir      : {failed_dir}")


if __name__ == "__main__":
    main()
