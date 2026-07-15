"""Batch ingestion pipeline: load files, validate, split into success/ and failed/."""

import hashlib
from pathlib import Path
from src.ingestion.registry import get_loader
from src.ingestion.schemas import Document
from src.preprocessing.validator import validate_record
from src.utils.config import RAW_DIR, SUCCESS_DIR, FAILED_DIR
from src.utils.logger import get_logger

logger = get_logger(__name__)


def ingest_file(file_path: Path) -> list[Document]:
    """Load a single file using the appropriate loader."""
    loader = get_loader(file_path)
    return loader.load(file_path)


def _content_hash(file_path: Path) -> str:
    """Return SHA-256 hex digest of file contents."""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def _load_error_document(file_path: Path, error: Exception) -> Document:
    """Return a failed-load placeholder so the file appears in failed output."""
    return Document(
        source_file=file_path.name,
        source_path=str(file_path),
        doc_type=file_path.suffix.lower().lstrip(".") or "unknown",
        text="",
        warnings=[f"Load error: {error}"],
    )


def _split_and_write(
    docs: list[Document],
    stem: str,
    success_dir: Path,
    failed_dir: Path,
) -> dict:
    """Validate each Document, write to success/ or failed/ JSONL.

    Returns per-file stats dict.
    """
    success_dir.mkdir(parents=True, exist_ok=True)
    failed_dir.mkdir(parents=True, exist_ok=True)

    success_records: list[dict] = []
    failed_records: list[dict] = []

    stats = {"total": len(docs), "success": 0, "failed": 0,
             "empty_text": 0, "garbled_text": 0, "has_warnings": 0, "needs_ocr": 0}

    for doc in docs:
        record = validate_record(doc.to_dict())
        if record["status"] == "success":
            stats["success"] += 1
            success_records.append(record)
        else:
            stats["failed"] += 1
            failed_records.append(record)
            if "empty_text" in record.get("failure_reasons", []):
                stats["empty_text"] += 1
            if "garbled_text" in record.get("failure_reasons", []):
                stats["garbled_text"] += 1
            if "has_warnings" in record.get("failure_reasons", []):
                stats["has_warnings"] += 1
            if record.get("needs_ocr"):
                stats["needs_ocr"] += 1

    if success_records:
        _write_jsonl(success_records, success_dir / f"{stem}.jsonl")
    if failed_records:
        _write_jsonl(failed_records, failed_dir / f"{stem}.jsonl")

    return stats


def ingest_directory(
    input_dir: Path | None = None,
    success_dir: Path | None = None,
    failed_dir: Path | None = None,
) -> dict:
    """Ingest all supported files in *input_dir*, validate each record, and write
    directly to *success_dir* and *failed_dir*.

    Files with identical content (same SHA-256 hash) to an already-processed
    file are skipped as duplicates.

    Returns aggregate stats dict.
    """
    input_dir = Path(input_dir) if input_dir else RAW_DIR
    success_dir = Path(success_dir) if success_dir else SUCCESS_DIR
    failed_dir = Path(failed_dir) if failed_dir else FAILED_DIR

    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    from src.ingestion.registry import supported_extensions

    exts = supported_extensions()
    logger.info("Supported extensions: %s", exts)
    logger.info("Scanning %s", input_dir)

    totals = {"files": 0, "total": 0, "success": 0, "failed": 0,
              "empty_text": 0, "garbled_text": 0, "has_warnings": 0, "needs_ocr": 0,
              "skipped_unsupported": 0, "skipped_duplicate": 0, "load_errors": 0}

    seen_hashes: dict[str, str] = {}

    for file_path in sorted(input_dir.iterdir()):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in exts:
            totals["skipped_unsupported"] += 1
            continue

        file_hash = _content_hash(file_path)
        if file_hash in seen_hashes:
            totals["skipped_duplicate"] += 1
            logger.warning(
                "Skipping %s (content identical to %s)",
                file_path.name, seen_hashes[file_hash],
            )
            continue
        seen_hashes[file_hash] = file_path.name

        try:
            docs = ingest_file(file_path)
            stem = file_path.stem
            file_stats = _split_and_write(docs, stem, success_dir, failed_dir)
            totals["files"] += 1
            for key in ("total", "success", "failed", "empty_text", "garbled_text", "has_warnings", "needs_ocr"):
                totals[key] += file_stats[key]
            logger.info(
                "%s: %d records — success=%d failed=%d",
                file_path.name, file_stats["total"],
                file_stats["success"], file_stats["failed"],
            )
        except Exception as e:
            logger.exception("Failed to ingest %s", file_path.name)
            totals["load_errors"] += 1
            file_stats = _split_and_write(
                [_load_error_document(file_path, e)],
                file_path.stem,
                success_dir,
                failed_dir,
            )
            totals["files"] += 1
            for key in ("total", "success", "failed", "empty_text", "garbled_text", "has_warnings", "needs_ocr"):
                totals[key] += file_stats[key]

    logger.info(
        "Done. %d files, %d records — success=%d failed=%d "
        "empty_text=%d garbled=%d warnings=%d needs_ocr=%d "
        "duplicates=%d unsupported=%d errors=%d.",
        totals["files"], totals["total"], totals["success"], totals["failed"],
        totals["empty_text"], totals["garbled_text"], totals["has_warnings"], totals["needs_ocr"],
        totals["skipped_duplicate"], totals["skipped_unsupported"], totals["load_errors"],
    )
    return totals


def _write_jsonl(records: list[dict], path: Path) -> None:
    import json
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
