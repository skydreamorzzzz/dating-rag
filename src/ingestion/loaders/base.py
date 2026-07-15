"""Abstract base class for document loaders."""

from abc import ABC, abstractmethod
from pathlib import Path
from src.ingestion.schemas import Document


class BaseLoader(ABC):
    """Every loader inherits from this and implements :meth:`load`."""

    @abstractmethod
    def load(self, file_path: Path) -> list[Document]:
        """Parse *file_path* and return one or more Documents."""
        ...

    @staticmethod
    def supported_extensions() -> list[str]:
        """Return lower-case extensions this loader handles (e.g. ``['.txt']``)."""
        return []
