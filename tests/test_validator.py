"""Tests for the quality validator."""

import json
import tempfile
from pathlib import Path

import pytest

from src.preprocessing.validator import validate_record, validate_file


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(**overrides) -> dict:
    base = {
        "source_file": "test.pdf",
        "source_path": "/data/raw/test.pdf",
        "doc_type": "pdf",
        "doc_id": "abc123",
        "text": "这是正常的文本内容。",
        "page": 1,
        "section": None,
        "warnings": [],
        "metadata": {},
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# validate_record
# ---------------------------------------------------------------------------

class TestValidateRecord:
    def test_clean_text_passes(self):
        rec = validate_record(_make_record())
        assert rec["status"] == "success"
        assert "failure_reasons" not in rec

    def test_empty_text_fails(self):
        rec = validate_record(_make_record(text="   "))
        assert rec["status"] == "failed"
        assert "empty_text" in rec["failure_reasons"]

    def test_null_text_fails(self):
        rec = validate_record(_make_record(text=None))
        assert rec["status"] == "failed"
        assert "null_text" in rec["failure_reasons"]

    def test_has_warnings_fails(self):
        rec = validate_record(_make_record(warnings=["Encoding issue"]))
        assert rec["status"] == "failed"
        assert "has_warnings" in rec["failure_reasons"]

    def test_missing_source_file_fails(self):
        rec = validate_record(_make_record(source_file=""))
        assert rec["status"] == "failed"
        assert "missing_source_file" in rec["failure_reasons"]

    def test_missing_doc_id_fails(self):
        rec = validate_record(_make_record(doc_id=None))
        assert rec["status"] == "failed"
        assert "missing_doc_id" in rec["failure_reasons"]

    def test_multiple_reasons(self):
        rec = validate_record(_make_record(
            text="", source_file="", warnings=["warn"],
        ))
        assert rec["status"] == "failed"
        reasons = rec["failure_reasons"]
        assert "empty_text" in reasons
        assert "missing_source_file" in reasons
        assert "has_warnings" in reasons

    def test_section_null_does_not_fail(self):
        """Optional fields (section, page) can be null."""
        rec = validate_record(_make_record(section=None, page=None))
        assert rec["status"] == "success"

    # --- needs_ocr ---

    def test_pdf_empty_text_needs_ocr(self):
        rec = validate_record(_make_record(doc_type="pdf", text=""))
        assert rec["status"] == "failed"
        assert rec["needs_ocr"] is True

    def test_pdf_ocr_warning_needs_ocr(self):
        rec = validate_record(_make_record(
            doc_type="pdf",
            text="some text",
            warnings=["All pages returned empty text — this PDF may be image-based (scanned), OCR required"],
        ))
        assert rec["status"] == "failed"
        assert rec["needs_ocr"] is True

    def test_txt_empty_text_no_ocr(self):
        rec = validate_record(_make_record(doc_type="txt", text=""))
        assert rec["status"] == "failed"
        assert rec["needs_ocr"] is False

    def test_non_pdf_warning_no_ocr(self):
        rec = validate_record(_make_record(
            doc_type="txt",
            warnings=["File decoded as gb18030, not utf-8"],
        ))
        assert rec["status"] == "failed"
        assert rec["needs_ocr"] is False

    # --- garbled_text ---

    def test_null_bytes_are_garbled(self):
        """UTF-16 mojibake: null bytes between ASCII chars."""
        rec = validate_record(_make_record(text="\x00P\x00D\x00F\x00 test"))
        assert rec["status"] == "failed"
        assert "garbled_text" in rec["failure_reasons"]

    def test_high_control_char_ratio_is_garbled(self):
        """>30% control/private-use characters → garbled."""
        # 10 normal chars + 10 control chars = 50% → garbled
        text = "hello" + "\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c" + "world"
        rec = validate_record(_make_record(text=text))
        assert rec["status"] == "failed"
        assert "garbled_text" in rec["failure_reasons"]

    def test_normal_text_not_garbled(self):
        rec = validate_record(_make_record(text="这是正常的聊天话题内容。"))
        assert rec["status"] == "success"

    def test_pdf_garbled_text_needs_ocr(self):
        rec = validate_record(_make_record(
            doc_type="pdf", text="\x00P\x00D\x00F",
        ))
        assert rec["status"] == "failed"
        assert "garbled_text" in rec["failure_reasons"]
        assert rec["needs_ocr"] is True

    def test_txt_garbled_no_ocr(self):
        """Garbled TXT doesn't imply OCR — it's an encoding problem."""
        rec = validate_record(_make_record(
            doc_type="txt", text="\x00hello",
        ))
        assert rec["status"] == "failed"
        assert rec["needs_ocr"] is False


# ---------------------------------------------------------------------------
# validate_file (integration)
# ---------------------------------------------------------------------------

class TestValidateFile:
    def test_splits_success_and_failed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            input_file = tmp / "input.jsonl"

            good = _make_record()
            bad_empty = _make_record(source_file="bad1.txt", doc_type="txt", text="")
            bad_warn = _make_record(source_file="bad2.txt", doc_type="txt",
                                     warnings=["broken"])

            input_file.write_text("\n".join([
                json.dumps(good, ensure_ascii=False),
                json.dumps(bad_empty, ensure_ascii=False),
                json.dumps(bad_warn, ensure_ascii=False),
            ]), encoding="utf-8")

            sdir = tmp / "success"
            fdir = tmp / "failed"
            stats = validate_file(input_file, sdir, fdir)

            assert stats["total"] == 3
            assert stats["success"] == 1
            assert stats["failed"] == 2
            assert stats["empty_text"] == 1
            assert stats["has_warnings"] == 1

            # Verify success output
            success_lines = (sdir / "input.jsonl").read_text().strip().split("\n")
            assert len(success_lines) == 1
            assert json.loads(success_lines[0])["status"] == "success"

            # Verify failed output
            failed_lines = (fdir / "input.jsonl").read_text().strip().split("\n")
            assert len(failed_lines) == 2
            for line in failed_lines:
                rec = json.loads(line)
                assert rec["status"] == "failed"

    def test_empty_input_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            input_file = tmp / "empty.jsonl"
            input_file.write_text("", encoding="utf-8")

            sdir = tmp / "success"
            fdir = tmp / "failed"
            stats = validate_file(input_file, sdir, fdir)

            assert stats["total"] == 0
            assert stats["success"] == 0
            assert stats["failed"] == 0

    def test_parse_error_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            input_file = tmp / "bad.jsonl"
            input_file.write_text('not valid json', encoding="utf-8")

            sdir = tmp / "success"
            fdir = tmp / "failed"
            stats = validate_file(input_file, sdir, fdir)

            assert stats["total"] == 1
            assert stats["failed"] == 1
            assert stats["parse_errors"] == 1
