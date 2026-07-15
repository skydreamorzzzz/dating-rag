"""Loader for EPUB files using the standard library."""

from html.parser import HTMLParser
from pathlib import Path
import posixpath
import zipfile
import xml.etree.ElementTree as ET

from src.ingestion.loaders.base import BaseLoader
from src.ingestion.schemas import Document
from src.utils.logger import get_logger

logger = get_logger(__name__)


class _TextExtractor(HTMLParser):
    """Small HTML text extractor for XHTML chapters inside EPUB archives."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"script", "style"}:
            self._skip_depth += 1
        if tag.lower() in {"p", "br", "div", "section", "article", "h1", "h2", "h3", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1
        if tag.lower() in {"p", "div", "section", "article", "h1", "h2", "h3", "li"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = data.strip()
        if text:
            self.parts.append(text)

    def text(self) -> str:
        lines = [" ".join(line.split()) for line in "".join(self.parts).splitlines()]
        return "\n".join(line for line in lines if line)


class EpubLoader(BaseLoader):
    """Load an .epub file, returning one Document per spine item."""

    def load(self, file_path: Path) -> list[Document]:
        try:
            with zipfile.ZipFile(file_path) as archive:
                opf_path = self._find_opf_path(archive)
                item_paths = self._spine_item_paths(archive, opf_path)
                docs = self._load_items(archive, file_path, item_paths)
        except zipfile.BadZipFile as e:
            raise ValueError(f"Failed to open EPUB {file_path.name}: not a valid zip archive") from e
        except KeyError as e:
            raise ValueError(f"Failed to open EPUB {file_path.name}: missing file {e}") from e
        except ET.ParseError as e:
            raise ValueError(f"Failed to parse EPUB metadata in {file_path.name}: {e}") from e

        if not docs:
            docs.append(
                Document(
                    source_file=file_path.name,
                    source_path=str(file_path),
                    doc_type="epub",
                    text="",
                    warnings=["No readable XHTML/HTML spine items found in EPUB"],
                )
            )

        logger.info("Loaded %s (%d sections)", file_path.name, len(docs))
        return docs

    def _find_opf_path(self, archive: zipfile.ZipFile) -> str:
        container = archive.read("META-INF/container.xml")
        root = ET.fromstring(container)
        for elem in root.iter():
            if elem.tag.endswith("rootfile"):
                path = elem.attrib.get("full-path")
                if path:
                    return path
        raise ValueError("EPUB container does not declare an OPF package")

    def _spine_item_paths(self, archive: zipfile.ZipFile, opf_path: str) -> list[str]:
        opf_root = ET.fromstring(archive.read(opf_path))
        manifest: dict[str, str] = {}
        spine_ids: list[str] = []

        for elem in opf_root.iter():
            if elem.tag.endswith("item"):
                item_id = elem.attrib.get("id")
                href = elem.attrib.get("href")
                media_type = elem.attrib.get("media-type", "")
                if item_id and href and media_type in {"application/xhtml+xml", "text/html"}:
                    manifest[item_id] = href
            elif elem.tag.endswith("itemref"):
                idref = elem.attrib.get("idref")
                if idref:
                    spine_ids.append(idref)

        base = posixpath.dirname(opf_path)
        paths: list[str] = []
        for item_id in spine_ids:
            href = manifest.get(item_id)
            if href:
                paths.append(posixpath.normpath(posixpath.join(base, href)))
        return paths

    def _load_items(
        self,
        archive: zipfile.ZipFile,
        file_path: Path,
        item_paths: list[str],
    ) -> list[Document]:
        docs: list[Document] = []
        for index, item_path in enumerate(item_paths, start=1):
            raw = archive.read(item_path)
            parser = _TextExtractor()
            parser.feed(raw.decode("utf-8", errors="replace"))
            text = parser.text()
            warnings: list[str] = []
            if not text:
                warnings.append("No text extracted from EPUB section")

            docs.append(
                Document(
                    source_file=file_path.name,
                    source_path=str(file_path),
                    doc_type="epub",
                    text=text,
                    section=item_path,
                    warnings=warnings,
                    metadata={"spine_index": index},
                )
            )
        return docs

    @staticmethod
    def supported_extensions() -> list[str]:
        return [".epub"]
