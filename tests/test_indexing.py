import importlib.util
import json
from pathlib import Path

import pytest

from src.indexing.embeddings import SentenceTransformerEmbedder
from src.indexing.vector_store import read_chunks, read_chunks_lenient, safe_metadata, validate_chunk


def _chunk(**overrides) -> dict:
    base = {
        "chunk_id": "chunk-1",
        "doc_id": "doc-1",
        "document_id": "doc-1",
        "text": "聊天话题内容",
        "source_file": "sample.txt",
        "source_path": "data/raw/sample.txt",
        "doc_type": "txt",
        "file_type": "txt",
        "page": None,
        "title": None,
        "section": None,
        "chunk_index": 0,
        "metadata": {"nested": {"x": 1}, "tags": ["a"]},
    }
    base.update(overrides)
    return base


def _load_inspect_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "inspect_chunks.py"
    spec = importlib.util.spec_from_file_location("inspect_chunks", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_build_index_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "build_index.py"
    spec = importlib.util.spec_from_file_location("build_index", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_search_index_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "search_index.py"
    spec = importlib.util.spec_from_file_location("search_index", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_query_instruction_is_added_once():
    embedder = SentenceTransformerEmbedder()

    formatted = embedder._format_query("如何聊天")
    assert formatted == "为这个句子生成表示以用于检索相关文章：如何聊天"
    assert embedder._format_query(formatted) == formatted


def test_safe_metadata_filters_null_and_serializes_complex_values():
    metadata = safe_metadata(_chunk(page=None, title=None, section=["第一节"]))

    assert "page" not in metadata
    assert "title" not in metadata
    assert metadata["section"] == '["第一节"]'
    assert metadata["doc_id"] == "doc-1"
    assert metadata["doc_type"] == "txt"
    assert metadata["source_file"] == "sample.txt"
    assert metadata["source_path"] == "data/raw/sample.txt"
    assert isinstance(metadata["original_metadata"], str)


def test_read_chunks_validates_required_index_fields(tmp_path):
    path = tmp_path / "chunks.jsonl"
    path.write_text(json.dumps(_chunk(), ensure_ascii=False) + "\n", encoding="utf-8")

    chunks = read_chunks(path)

    assert len(chunks) == 1
    assert chunks[0]["chunk_id"] == "chunk-1"


def test_validate_chunk_rejects_empty_text():
    with pytest.raises(ValueError, match="missing text"):
        validate_chunk(_chunk(text=" "))


def test_read_chunks_lenient_reads_directory_and_counts_bad_rows(tmp_path):
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    (chunks_dir / "a.jsonl").write_text(
        json.dumps(_chunk(chunk_id="a"), ensure_ascii=False) + "\n{bad json}\n",
        encoding="utf-8",
    )
    (chunks_dir / "b.jsonl").write_text(
        json.dumps(_chunk(chunk_id="b"), ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    chunks, errors = read_chunks_lenient(chunks_dir)

    assert [chunk["chunk_id"] for chunk in chunks] == ["a", "b"]
    assert errors == 1


def test_inspect_chunks_detects_duplicate_ids_and_missing_fields(tmp_path):
    inspect_chunks = _load_inspect_module()
    path = tmp_path / "chunks.jsonl"
    rows = [
        _chunk(chunk_id="same", text="正文一"),
        _chunk(chunk_id="same", document_id="", text="正文二"),
    ]
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )

    stats, by_source = inspect_chunks.inspect_chunks(path)

    assert stats["total"] == 2
    assert stats["duplicate_chunk_id"] == 1
    assert stats["missing_required"]["document_id"] == 1
    assert inspect_chunks.has_serious_issues(stats) is True
    assert by_source["sample.txt"] == 2


def test_chroma_vector_store_retrieves_with_fake_embeddings(tmp_path):
    chromadb = pytest.importorskip("chromadb")
    from src.indexing.vector_store import ChromaVectorStore

    store = ChromaVectorStore(persist_dir=tmp_path, collection_name="test_chunks")
    store.reset_collection()
    chunks = [
        _chunk(chunk_id="chat", text="聊天技巧", chunk_index=0),
        _chunk(chunk_id="date", text="约会安排", chunk_index=1),
    ]
    store.upsert_chunks(chunks, [[1.0, 0.0], [0.0, 1.0]])

    results = store.query([1.0, 0.0], top_k=1)

    assert results[0]["chunk_id"] == "chat"
    assert results[0]["text"] == "聊天技巧"
    assert results[0]["metadata"]["source_file"] == "sample.txt"


def test_build_index_skips_existing_and_duplicate_ids(monkeypatch, tmp_path):
    build_index_module = _load_build_index_module()
    chunks_path = tmp_path / "chunks.jsonl"
    rows = [
        _chunk(chunk_id="existing", text="已有内容"),
        _chunk(chunk_id="new", text="新增内容"),
        _chunk(chunk_id="new", text="重复内容"),
        _chunk(chunk_id="", text="坏内容"),
    ]
    chunks_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )

    class FakeEmbedder:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def encode_documents(self, texts):
            return [[float(len(text)), 0.0] for text in texts]

    class FakeStore:
        def __init__(self, **kwargs):
            self.ids = {"existing"}

        def reset_collection(self):
            self.ids.clear()

        def existing_ids(self, ids):
            return self.ids.intersection(set(ids))

        def upsert_chunks(self, chunks, embeddings):
            assert len(chunks) == len(embeddings)
            for chunk in chunks:
                self.ids.add(chunk["chunk_id"])
            return len(chunks)

        def count(self):
            return len(self.ids)

    monkeypatch.setattr(build_index_module, "SentenceTransformerEmbedder", FakeEmbedder)
    monkeypatch.setattr(build_index_module, "ChromaVectorStore", FakeStore)

    stats = build_index_module.build_index(
        chunks_path=chunks_path,
        persist_dir=tmp_path / "vectors",
        collection_name="test",
        model_name="fake",
        batch_size=2,
        normalize_embeddings=True,
        rebuild=False,
    )

    assert stats == {
        "chunks": 3,
        "success": 1,
        "failed": 1,
        "skipped": 2,
        "total_vectors": 2,
    }


def test_search_index_embeds_query_and_returns_results(monkeypatch, tmp_path):
    search_index_module = _load_search_index_module()

    class FakeEmbedder:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def encode_query(self, question):
            assert question == "如何聊天"
            return [1.0, 0.0]

    class FakeStore:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def query(self, query_embedding, top_k):
            assert query_embedding == [1.0, 0.0]
            assert top_k == 3
            return [{"chunk_id": "chat", "text": "聊天内容", "metadata": {}, "distance": 0.1}]

    monkeypatch.setattr(search_index_module, "SentenceTransformerEmbedder", FakeEmbedder)
    monkeypatch.setattr(search_index_module, "ChromaVectorStore", FakeStore)

    results = search_index_module.search_index(
        question="如何聊天",
        persist_dir=tmp_path,
        collection_name="test",
        model_name="fake",
        batch_size=2,
        top_k=3,
    )

    assert results[0]["chunk_id"] == "chat"
