"""Build deterministic text chunks from validated success records."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Iterable, Iterator

from src.preprocessing.cleaner import clean_text
from src.utils.config import CHUNKS_DIR, SUCCESS_DIR

DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 50
SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[。！？!?；;])")


def build_chunks_from_success(
    success_dir: Path = SUCCESS_DIR,
    output_path: Path | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> dict:
    """Read validated success records and write deterministic chunk JSONL."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if chunk_overlap < 0:
        raise ValueError("chunk_overlap must be non-negative")
    if chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be smaller than chunk_size")

    success_dir = Path(success_dir)
    output_path = Path(output_path) if output_path else CHUNKS_DIR / "chunks.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    stats = {"records": 0, "documents": 0, "chunks": 0, "skipped": 0, "errors": 0}
    chunks: list[dict] = []

    for input_path in _iter_input_files(success_dir):
        for record, error in read_records_with_errors(input_path):
            if error is not None:
                stats["errors"] += 1
                continue
            if record is None:
                continue

            stats["records"] += 1
            try:
                if record.get("status") != "success":
                    stats["skipped"] += 1
                    continue

                text = clean_text(record.get("text"))
                if not text:
                    stats["skipped"] += 1
                    continue

                stats["documents"] += 1
                doc_chunks = chunk_record(record, chunk_size, chunk_overlap)
                if not doc_chunks:
                    stats["skipped"] += 1
                    continue
                chunks.extend(doc_chunks)
                stats["chunks"] += len(doc_chunks)
            except Exception:
                stats["errors"] += 1

    write_chunks(chunks, output_path)
    return stats


def read_records(path: Path) -> Iterable[dict]:
    """Yield records from JSONL, JSON list, or single JSON object files."""
    for record, error in read_records_with_errors(path):
        if error is not None:
            raise error
        if record is not None:
            yield record


def read_records_with_errors(path: Path) -> Iterator[tuple[dict | None, Exception | None]]:
    """Yield parsed records while isolating malformed lines or files."""
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                    except Exception as exc:
                        yield None, exc
                        continue
                    if isinstance(data, dict):
                        yield data, None
                    else:
                        yield None, ValueError("JSONL line is not an object")
        return

    if suffix == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            yield None, exc
            return
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    yield item, None
                else:
                    yield None, ValueError("JSON list item is not an object")
        elif isinstance(data, dict):
            yield data, None
        else:
            yield None, ValueError("JSON file is not an object or list")


def chunk_record(
    record: dict,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict]:
    """Create chunk records for one validated document record."""
    text = clean_text(record.get("text"))
    pieces = split_text(text, chunk_size, chunk_overlap)
    chunks: list[dict] = []

    doc_id = record.get("doc_id") or record.get("document_id")
    source_file = record.get("source_file")
    source_path = record.get("source_path")
    doc_type = record.get("doc_type") or record.get("file_type")
    title = record.get("title")
    section = record.get("section")
    page = record.get("page")
    metadata = record.get("metadata") if isinstance(record.get("metadata"), dict) else {}

    for index, piece in enumerate(pieces):
        piece = clean_text(piece)
        if not piece:
            continue
        chunk = {
            "chunk_id": make_chunk_id(doc_id, source_path or source_file, page, section, index, piece),
            "doc_id": doc_id,
            "document_id": doc_id,
            "text": piece,
            "source_file": source_file,
            "source_path": source_path,
            "doc_type": doc_type,
            "file_type": doc_type,
            "page": page,
            "title": title,
            "section": section,
            "chunk_index": index,
            "metadata": metadata,
        }
        chunks.append(chunk)

    return chunks


def split_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    """Split text near paragraph and sentence boundaries with overlap."""
    text = clean_text(text)
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    units = _semantic_units(text, chunk_size)
    base_chunks: list[str] = []
    current = ""

    for unit in units:
        candidate = _join_unit(current, unit)
        if current and len(candidate) > chunk_size:
            base_chunks.append(current)
            current = unit
        else:
            current = candidate

    if current:
        base_chunks.append(current)

    if not base_chunks or chunk_overlap == 0:
        return base_chunks

    overlapped = [base_chunks[0]]
    for previous, chunk in zip(base_chunks, base_chunks[1:]):
        prefix = _overlap_tail(previous, chunk_overlap)
        overlapped.append(_join_unit(prefix, chunk) if prefix else chunk)
    return overlapped


def make_chunk_id(
    document_id: object,
    source_file: object,
    page: object,
    section: object,
    chunk_index: int,
    text: str,
) -> str:
    """Return a stable chunk id derived from source identity and chunk text."""
    payload = json.dumps(
        {
            "document_id": document_id,
            "source_file": source_file,
            "page": page,
            "section": section,
            "chunk_index": chunk_index,
            "text": text,
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:20]


def write_chunks(chunks: list[dict], output_path: Path) -> None:
    """Write chunks to JSONL, replacing previous output."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False, sort_keys=True) + "\n")


def _iter_input_files(success_dir: Path) -> Iterable[Path]:
    if not success_dir.exists():
        raise FileNotFoundError(f"Success directory does not exist: {success_dir}")
    yield from sorted(
        path for path in success_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".jsonl", ".json"}
    )


def _semantic_units(text: str, chunk_size: int) -> list[str]:
    units: list[str] = []
    for paragraph in re.split(r"\n{2,}", text):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        for line in paragraph.split("\n"):
            line = line.strip()
            if not line:
                continue
            for sentence in SENTENCE_BOUNDARY_RE.split(line):
                sentence = sentence.strip()
                if not sentence:
                    continue
                units.extend(_hard_split(sentence, chunk_size))
    return units


def _hard_split(text: str, chunk_size: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text]
    return [text[start:start + chunk_size] for start in range(0, len(text), chunk_size)]


def _join_unit(left: str, right: str) -> str:
    if not left:
        return right.strip()
    if not right:
        return left.strip()
    separator = "\n" if "\n" in left or "\n" in right else " "
    return f"{left.rstrip()}{separator}{right.lstrip()}".strip()


def _overlap_tail(text: str, size: int) -> str:
    if size <= 0:
        return ""
    if len(text) <= size:
        return text
    tail = text[-size:]
    for marker in ("。", "！", "？", "\n", " "):
        pos = tail.find(marker)
        if 0 <= pos < len(tail) - 1:
            return tail[pos + 1:].strip()
    return tail.strip()
