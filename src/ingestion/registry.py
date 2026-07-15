"""Extension-to-loader registry so callers don't pick loaders manually."""

from pathlib import Path
from src.ingestion.loaders.base import BaseLoader
from src.ingestion.loaders.txt_loader import TxtLoader
from src.ingestion.loaders.pdf_loader import PdfLoader
from src.ingestion.loaders.docx_loader import DocxLoader
from src.ingestion.loaders.pptx_loader import PptxLoader
from src.ingestion.loaders.epub_loader import EpubLoader
from src.ingestion.loaders.legacy_office_loader import DocLoader, PptLoader
from src.utils.logger import get_logger

logger = get_logger(__name__)

_LOADERS: list[type[BaseLoader]] = [
    TxtLoader,
    PdfLoader,
    DocxLoader,
    PptxLoader,
    EpubLoader,
    DocLoader,
    PptLoader,
]

_registry: dict[str, type[BaseLoader]] = {}

_initialized = False


def _build_registry() -> None:
    global _initialized
    if _initialized:
        return
    for loader_cls in _LOADERS:
        for ext in loader_cls.supported_extensions():
            _registry[ext.lower()] = loader_cls
    _initialized = True


def get_loader(file_path: Path) -> BaseLoader:
    """Return the appropriate loader instance for *file_path* based on suffix."""
    _build_registry()
    ext = file_path.suffix.lower()
    loader_cls = _registry.get(ext)
    if loader_cls is None:
        raise ValueError(f"No loader registered for extension '{ext}' ({file_path.name})")
    return loader_cls()


def supported_extensions() -> list[str]:
    """Return all file extensions that have a registered loader."""
    _build_registry()
    return sorted(_registry.keys())
