import zipfile
from pathlib import Path

from src.ingestion.loaders.epub_loader import EpubLoader
from src.ingestion.loaders.legacy_office_loader import DocLoader
from src.ingestion.registry import get_loader, supported_extensions
from src.ingestion.schemas import Document


def test_registry_supports_initial_mvp_formats():
    assert supported_extensions() == [".doc", ".docx", ".epub", ".pdf", ".ppt", ".pptx", ".txt"]


def test_get_loader_for_legacy_doc():
    loader = get_loader(Path("sample.doc"))

    assert isinstance(loader, DocLoader)


def test_epub_loader_extracts_spine_text(tmp_path):
    epub_path = tmp_path / "sample.epub"
    with zipfile.ZipFile(epub_path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr(
            "META-INF/container.xml",
            """<?xml version="1.0"?>
            <container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
              <rootfiles>
                <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
              </rootfiles>
            </container>""",
        )
        archive.writestr(
            "OEBPS/content.opf",
            """<?xml version="1.0"?>
            <package xmlns="http://www.idpf.org/2007/opf" version="3.0">
              <manifest>
                <item id="chapter1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
              </manifest>
              <spine>
                <itemref idref="chapter1"/>
              </spine>
            </package>""",
        )
        archive.writestr(
            "OEBPS/chapter1.xhtml",
            "<html><body><h1>标题</h1><p>第一段内容。</p><p>第二段内容。</p></body></html>",
        )

    docs = EpubLoader().load(epub_path)

    assert len(docs) == 1
    assert docs[0].doc_type == "epub"
    assert docs[0].source_file == "sample.epub"
    assert docs[0].section == "OEBPS/chapter1.xhtml"
    assert "第一段内容" in docs[0].text
    assert docs[0].warnings == []


def test_doc_loader_preserves_original_source_after_conversion(monkeypatch, tmp_path):
    source = tmp_path / "legacy.doc"
    converted = tmp_path / "legacy.docx"
    source.write_bytes(b"legacy")
    converted.write_bytes(b"converted")

    def fake_convert(path):
        assert path == source
        return converted

    def fake_load(self, path):
        assert path == converted
        return [
            Document(
                source_file=converted.name,
                source_path=str(converted),
                doc_type="docx",
                text="converted text",
            )
        ]

    monkeypatch.setattr("src.ingestion.loaders.legacy_office_loader.convert_with_libreoffice", fake_convert)
    monkeypatch.setattr("src.ingestion.loaders.legacy_office_loader.DocxLoader.load", fake_load)

    docs = DocLoader().load(source)

    assert len(docs) == 1
    assert docs[0].source_file == "legacy.doc"
    assert docs[0].source_path == str(source)
    assert docs[0].doc_type == "doc"
    assert docs[0].text == "converted text"
    assert docs[0].metadata["converted_path"] == str(converted)
    assert docs[0].metadata["converted_doc_type"] == "docx"
