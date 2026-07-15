"""Loaders for legacy DOC/PPT files via LibreOffice conversion."""

from pathlib import Path

from src.ingestion.converters.libreoffice import convert_with_libreoffice
from src.ingestion.loaders.base import BaseLoader
from src.ingestion.loaders.docx_loader import DocxLoader
from src.ingestion.loaders.pptx_loader import PptxLoader
from src.ingestion.schemas import Document


class DocLoader(BaseLoader):
    """Convert .doc to .docx, then reuse the DOCX loader."""

    def load(self, file_path: Path) -> list[Document]:
        converted = convert_with_libreoffice(file_path)
        docs = DocxLoader().load(converted)
        return [_with_original_source(doc, file_path, "doc", converted) for doc in docs]

    @staticmethod
    def supported_extensions() -> list[str]:
        return [".doc"]


class PptLoader(BaseLoader):
    """Convert .ppt to .pptx, then reuse the PPTX loader."""

    def load(self, file_path: Path) -> list[Document]:
        converted = convert_with_libreoffice(file_path)
        docs = PptxLoader().load(converted)
        return [_with_original_source(doc, file_path, "ppt", converted) for doc in docs]

    @staticmethod
    def supported_extensions() -> list[str]:
        return [".ppt"]


def _with_original_source(
    doc: Document,
    original_path: Path,
    doc_type: str,
    converted_path: Path,
) -> Document:
    metadata = dict(doc.metadata)
    metadata.update(
        {
            "converted_from": str(original_path),
            "converted_path": str(converted_path),
            "converted_doc_type": doc.doc_type,
        }
    )
    doc.source_file = original_path.name
    doc.source_path = str(original_path)
    doc.doc_type = doc_type
    doc.metadata = metadata
    return doc
