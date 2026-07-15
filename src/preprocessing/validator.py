"""Quality validation: split records into success/ and failed/ based on content rules."""

import json
import unicodedata
from pathlib import Path
from src.utils.logger import get_logger

logger = get_logger(__name__)

REQUIRED_FIELDS = ["source_file", "source_path", "doc_type", "doc_id"]

# Characters in these Unicode categories are never expected in clean extracted text
# Cc = control (except common whitespace: \t \n \r)
# Co = private use
# Cs = surrogate (should never appear in valid UTF-8/UTF-32 text)
_SUSPECT_CATEGORIES = frozenset(["Cc", "Co", "Cs"])

# Ratio of suspect characters above which text is considered garbled
_GARBLED_RATIO_THRESHOLD = 0.3


def validate_record(record: dict) -> dict:
    """Validate a single record dict. Returns the record enriched with ``status``,
    and ``failure_reasons`` / ``needs_ocr`` when applicable.

    The input dict is mutated in place.
    """
    reasons: list[str] = []
    needs_ocr = False

    # --- required fields ---
    for field in REQUIRED_FIELDS:
        if not record.get(field):
            reasons.append(f"missing_{field}")

    # --- text checks ---
    text = record.get("text")
    if text is None:
        reasons.append("null_text")
    elif not isinstance(text, str):
        reasons.append("invalid_text_type")
    elif not text.strip():
        reasons.append("empty_text")
    elif _is_garbled(text):
        reasons.append("garbled_text")

    # --- warnings ---
    if record.get("warnings"):
        reasons.append("has_warnings")

    # --- needs_ocr detection ---
    if _needs_ocr(record):
        needs_ocr = True

    if reasons:
        record["status"] = "failed"
        record["failure_reasons"] = reasons
        record["needs_ocr"] = needs_ocr
    else:
        record["status"] = "success"

    return record


def _is_garbled(text: str) -> bool:
    """Return True if *text* looks like mojibake / encoding corruption.

    Signals:
    - Null bytes (classic sign of UTF-16 bytes misread as 8-bit chars)
    - High ratio of characters in suspect Unicode categories (control,
      private-use, surrogates) relative to total non-whitespace characters
    """
    # Null bytes are a dead giveaway — no clean extracted text should contain them
    if "\x00" in text:
        return True

    non_ws = [c for c in text if not unicodedata.category(c).startswith("Z")]
    if not non_ws:
        return False

    suspect = sum(1 for c in non_ws if unicodedata.category(c) in _SUSPECT_CATEGORIES)
    ratio = suspect / len(non_ws)
    return ratio > _GARBLED_RATIO_THRESHOLD


def _needs_ocr(record: dict) -> bool:
    """Return True if the record likely needs OCR."""
    text = record.get("text")
    empty_text = text is None or (isinstance(text, str) and not text.strip())

    # PDF with empty text → likely scanned
    if record.get("doc_type") == "pdf" and empty_text:
        return True

    # Garbled text from PDF → likely encoding issue from scanned/image content
    if record.get("doc_type") == "pdf" and isinstance(text, str) and _is_garbled(text):
        return True

    # Any warning mentioning OCR or image-based
    for w in record.get("warnings", []):
        wl = w.lower()
        if any(kw in wl for kw in ("ocr", "image-based", "scanned")):
            return True

    return False


def validate_file(
    input_path: Path,
    success_dir: Path,
    failed_dir: Path,
) -> dict:
    """Validate one JSONL file, writing qualified records to *success_dir*
    and failing records to *failed_dir*.

    Returns stats dict with keys: total, success, failed, empty_text, has_warnings, needs_ocr.
    """
    success_dir.mkdir(parents=True, exist_ok=True)
    failed_dir.mkdir(parents=True, exist_ok=True)

    stats = {
        "total": 0,
        "success": 0,
        "failed": 0,
        "empty_text": 0,
        "garbled_text": 0,
        "has_warnings": 0,
        "needs_ocr": 0,
        "parse_errors": 0,
    }

    success_records: list[dict] = []
    failed_records: list[dict] = []

    with open(input_path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue

            stats["total"] += 1

            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("%s:%d — JSON parse error, skipping", input_path.name, line_no)
                stats["parse_errors"] += 1
                stats["failed"] += 1
                failed_records.append({
                    "status": "failed",
                    "failure_reasons": ["parse_error"],
                    "needs_ocr": False,
                    "source_file": input_path.name,
                    "line": line_no,
                })
                continue

            record = validate_record(record)

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

    # Write outputs only if there are records
    if success_records:
        _write_jsonl(success_records, success_dir / input_path.name)
    if failed_records:
        _write_jsonl(failed_records, failed_dir / input_path.name)

    return stats


def validate_directory(
    input_dir: Path,
    success_dir: Path,
    failed_dir: Path,
) -> dict:
    """Validate all JSONL files in *input_dir*.

    Returns aggregate stats across all files.
    """
    if not input_dir.exists():
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")

    jsonl_files = sorted(input_dir.glob("*.jsonl"))
    if not jsonl_files:
        logger.warning("No .jsonl files found in %s", input_dir)
        return {}

    logger.info("Validating %d files from %s", len(jsonl_files), input_dir)

    totals = {"files": len(jsonl_files), "total": 0, "success": 0, "failed": 0,
              "empty_text": 0, "garbled_text": 0, "has_warnings": 0,
              "needs_ocr": 0, "parse_errors": 0}

    for fp in jsonl_files:
        file_stats = validate_file(fp, success_dir, failed_dir)
        for key in totals:
            if key in file_stats:
                totals[key] += file_stats[key]

    logger.info(
        "Validation complete. %d files, %d records — success=%d failed=%d "
        "empty_text=%d garbled=%d warnings=%d needs_ocr=%d parse_errors=%d",
        totals["files"], totals["total"], totals["success"], totals["failed"],
        totals["empty_text"], totals["garbled_text"], totals["has_warnings"],
        totals["needs_ocr"], totals["parse_errors"],
    )
    return totals


def _write_jsonl(records: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
