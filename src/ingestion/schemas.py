"""Unified document structure for all loaders."""

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
import json
import uuid


@dataclass
class Document:
    """Internal representation of a loaded document.

    All loaders must return this structure (or a list of them for multi-page docs).
    """

    source_file: str
    source_path: str
    doc_type: str
    text: str
    doc_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    page: Optional[int] = None
    section: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Document":
        return cls(**d)


def write_jsonl(docs: list[Document], output_path: Path) -> None:
    """Write documents to a JSONL file, one JSON object per line."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc.to_dict(), ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[Document]:
    """Read documents from a JSONL file."""
    docs = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                docs.append(Document.from_dict(json.loads(line)))
    return docs
