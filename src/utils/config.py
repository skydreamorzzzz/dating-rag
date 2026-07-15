"""Centralised configuration. Non-secret values live here; secrets in env vars."""

from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
SAMPLES_DIR = DATA_DIR / "samples"
CHUNKS_DIR = DATA_DIR / "chunks"
VECTOR_STORE_DIR = DATA_DIR / "vector_store"

DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
DEFAULT_EMBEDDING_BATCH_SIZE = 32
DEFAULT_NORMALIZE_EMBEDDINGS = True
DEFAULT_QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："
DEFAULT_CHROMA_COLLECTION = "dating_rag_chunks"

# Validation outputs
SUCCESS_DIR = PROCESSED_DIR / "success"
FAILED_DIR = PROCESSED_DIR / "failed"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
INTERIM_DIR.mkdir(parents=True, exist_ok=True)
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)
VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
