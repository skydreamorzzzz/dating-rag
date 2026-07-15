# dating-rag

MVP Retrieval-Augmented Generation project for ingesting dating/relationship
documents, validating extracted text quality, and preparing clean records for
later chunking, indexing, retrieval, and DeepSeek-backed answer generation.

## Current Ingestion Support

Supported input formats:

- `.txt`
- `.pdf`
- `.docx`
- `.doc` via LibreOffice conversion to `.docx`
- `.pptx`
- `.ppt` via LibreOffice conversion to `.pptx`
- `.epub`

Legacy `.doc` and `.ppt` files require LibreOffice to be installed in WSL. The
converted files are written to `data/interim/`; output records still preserve
the original source file and path.

## Setup

```bash
python -m pip install -r requirements.txt
sudo apt install libreoffice
```

## Ingest Documents

Put documents in `data/raw/`, then run:

```bash
python scripts/ingest.py
```

To ingest one file or another directory:

```bash
python scripts/ingest.py data/raw/example.doc
python scripts/ingest.py data/raw/
```

Validated output is split into:

- `data/processed/success/`
- `data/processed/failed/`

PDF pages or slides/sections that contain only images are preserved as failed
records with warnings where possible, so later OCR work can target them.

## Build Chunks

Chunking reads only validated records from `data/processed/success/` and writes
deterministic JSONL to `data/chunks/chunks.jsonl`.

```bash
python scripts/build_chunks.py
```

Optional parameters:

```bash
python scripts/build_chunks.py --chunk-size 500 --chunk-overlap 50
python scripts/build_chunks.py --input-dir data/processed/success --output data/chunks/chunks.jsonl
```

Defaults are about 500 Chinese characters per chunk with about 50 characters of
overlap. Cleaning is conservative: it normalizes newlines and extra whitespace
without dropping meaningful source text. Re-running the command overwrites the
same output file instead of appending duplicates.

## Inspect Chunks

Before building embeddings, inspect chunk quality:

```bash
python scripts/inspect_chunks.py
```

The script reports chunk counts, empty text, missing IDs, duplicate IDs,
duplicate exact text, text length statistics, missing required fields, and the
largest source files by chunk count. It exits non-zero for blocking issues such
as empty text, duplicate `chunk_id`, or missing required fields. `title`,
`section`, and `page` may be null.

## Build Vector Index

The first vector index uses `sentence-transformers` with
`BAAI/bge-small-zh-v1.5` and persists a Chroma collection to
`data/vector_store/`.

```bash
python scripts/build_index.py --rebuild
```

Useful options:

```bash
python scripts/build_index.py --batch-size 32
python scripts/build_index.py --collection dating_rag_chunks
python scripts/build_index.py --model BAAI/bge-small-zh-v1.5
```

The index stores `chunk_id` as the Chroma id, chunk text as the document, and
safe metadata such as `document_id`, `source_file`, `file_type`, `chunk_index`,
`page`, `title`, and `section` when present.
