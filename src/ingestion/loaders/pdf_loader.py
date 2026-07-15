"""Loader for PDF files via pypdf, with per-page extraction."""

from pathlib import Path
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from src.ingestion.loaders.base import BaseLoader
from src.ingestion.schemas import Document
from src.utils.logger import get_logger

logger = get_logger(__name__)


class PdfLoader(BaseLoader):
    """Load a .pdf file, returning one Document per page.

    Image-based (scanned) PDFs produce pages with empty text and a warning.
    """

    def load(self, file_path: Path) -> list[Document]:
        try:
            reader = PdfReader(str(file_path))
        except (PdfReadError, Exception) as e:
            raise ValueError(f"Failed to open PDF {file_path.name}: {e}") from e

        total_pages = len(reader.pages)
        docs: list[Document] = []
        empty_pages = 0

        for i, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text()
            except Exception:
                logger.warning("%s page %d: extraction error", file_path.name, i)
                text = ""

            cleaned = text.strip() if text else ""
            if not cleaned:
                empty_pages += 1

            doc = Document(
                source_file=file_path.name,
                source_path=str(file_path),
                doc_type="pdf",
                text=cleaned,
                page=i,
            )
            docs.append(doc)

        total_chars = sum(len(d.text) for d in docs)
        if empty_pages == total_pages:
            docs[0].warnings.append(
                "All pages returned empty text — this PDF may be image-based (scanned), OCR required"
            )
            logger.warning("%s: all %d pages empty (image-based?)", file_path.name, total_pages)
        elif empty_pages > 0:
            logger.warning("%s: %d/%d pages empty", file_path.name, empty_pages, total_pages)

        logger.info(
            "Loaded %s (%d pages, %d chars, %d empty)",
            file_path.name, total_pages, total_chars, empty_pages,
        )
        return docs

    @staticmethod
    def supported_extensions() -> list[str]:
        return [".pdf"]
