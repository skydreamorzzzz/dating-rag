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
