import json
from pathlib import Path

from src.preprocessing.chunker import build_chunks_from_success, chunk_record, split_text
from src.preprocessing.cleaner import clean_text


def _record(**overrides) -> dict:
    base = {
        "doc_id": "doc-1",
        "source_file": "sample.pdf",
        "source_path": "/data/raw/sample.pdf",
        "doc_type": "pdf",
        "text": "第一段内容。",
        "page": None,
        "title": None,
        "section": None,
        "warnings": [],
        "metadata": {"author": "unknown"},
        "status": "success",
    }
    base.update(overrides)
    return base


def test_title_section_page_null_are_preserved():
    chunks = chunk_record(_record(title=None, section=None, page=None))

    assert len(chunks) == 1
    assert chunks[0]["title"] is None
    assert chunks[0]["section"] is None
    assert chunks[0]["page"] is None
    assert chunks[0]["document_id"] == "doc-1"


def test_short_text_produces_single_chunk():
    chunks = chunk_record(_record(text="短文本。"))

    assert len(chunks) == 1
    assert chunks[0]["text"] == "短文本。"
    assert chunks[0]["chunk_index"] == 0


def test_long_text_uses_overlap():
    text = "第一句很长。" * 20
    chunks = split_text(text, chunk_size=40, chunk_overlap=10)

    assert len(chunks) > 1
    assert chunks[0][-10:].strip() in chunks[1]


def test_clean_text_normalizes_extra_whitespace_and_newlines():
    text = " 第一行  有  空格\r\n\r\n\r\n 第二行\t有制表符 "

    assert clean_text(text) == "第一行 有 空格\n\n第二行 有制表符"


def test_empty_chunk_not_written_for_whitespace_text():
    chunks = chunk_record(_record(text=" \n\t "))

    assert chunks == []


def test_build_chunks_reads_only_success_dir(tmp_path):
    success_dir = tmp_path / "processed" / "success"
    failed_dir = tmp_path / "processed" / "failed"
    output_path = tmp_path / "chunks" / "chunks.jsonl"
    success_dir.mkdir(parents=True)
    failed_dir.mkdir(parents=True)

    success_record = _record(doc_id="success-doc", text="成功文本。")
    failed_record = _record(doc_id="failed-doc", text="失败文本。", status="failed")
    (success_dir / "success.jsonl").write_text(
        json.dumps(success_record, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (failed_dir / "failed.jsonl").write_text(
        json.dumps(failed_record, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    stats = build_chunks_from_success(success_dir=success_dir, output_path=output_path)
    lines = output_path.read_text(encoding="utf-8").strip().splitlines()

    assert stats["documents"] == 1
    assert stats["chunks"] == 1
    assert len(lines) == 1
    chunk = json.loads(lines[0])
    assert chunk["document_id"] == "success-doc"
    assert "失败文本" not in lines[0]


def test_build_chunks_overwrites_output(tmp_path):
    success_dir = tmp_path / "success"
    output_path = tmp_path / "chunks.jsonl"
    success_dir.mkdir()
    (success_dir / "doc.jsonl").write_text(
        json.dumps(_record(text="固定文本。"), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    first = build_chunks_from_success(success_dir=success_dir, output_path=output_path)
    first_output = output_path.read_text(encoding="utf-8")
    second = build_chunks_from_success(success_dir=success_dir, output_path=output_path)
    second_output = output_path.read_text(encoding="utf-8")

    assert first == second
    assert first_output == second_output
