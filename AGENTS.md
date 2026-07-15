# AGENTS.md

## Project Overview

`dating-rag` is a Retrieval-Augmented Generation project for searching and analyzing dating and relationship materials.

The project ingests documents, converts them into clean text chunks, stores embeddings in a vector database, retrieves relevant passages, and uses the DeepSeek API to generate grounded answers with source citations.

The source materials may contain low-quality advice, bias, pseudoscience, manipulative dating strategies, or contradictory claims. The system must treat retrieved content as source material rather than verified truth.

## Current Project Stage

The project is currently in the MVP/demo stage.

The immediate goal is to build a minimal end-to-end pipeline:

1. Load documents (→ `data/processed/*.jsonl`).
2. Validate quality and split into success/failed (→ `data/processed/success/`, `data/processed/failed/`).
3. Clean and split text (reads from `success/`).
4. Generate embeddings.
5. Build and persist a vector index.
6. Retrieve relevant chunks.
7. Send retrieved context to DeepSeek.
8. Return an answer with source information.

Do not introduce unnecessary production complexity before the demo pipeline works.

## Development Environment

* Operating system: WSL
* Language: Python 3.12
* LLM provider: DeepSeek API
* Initial document formats:

  * PDF
  * DOC (via LibreOffice conversion to DOCX)
  * DOCX
  * PPT (via LibreOffice conversion to PPTX)
  * PPTX
  * TXT
  * EPUB
* Future formats may include images, audio, and video, but they are currently out of scope.

## Expected Repository Structure

```text
dating-rag/
├── AGENTS.md
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── data/
│   ├── raw/                       # 原始文件
│   ├── interim/                   # doc→docx、ppt→pptx 等中间文件
│   ├── processed/                 # 标准化后的 JSONL
│   │   ├── success/                # 校验通过的记录
│   │   └── failed/                 # 校验失败的记录
│   └── samples/                   # 测试用公开样例
│
├── src/
│   ├── ingestion/
│   │   ├── schemas.py             # 统一数据结构
│   │   ├── registry.py            # 根据扩展名选择 loader
│   │   ├── pipeline.py            # 批量解析流程
│   │   │
│   │   ├── loaders/
│   │   │   ├── base.py
│   │   │   ├── txt_loader.py
│   │   │   ├── pdf_loader.py
│   │   │   ├── docx_loader.py
│   │   │   ├── pptx_loader.py
│   │   │   └── epub_loader.py
│   │   │
│   │   └── converters/
│   │       └── libreoffice.py     # doc/ppt 转换
│   │
│   ├── preprocessing/
│   │   ├── validator.py           # 质量校验与分流
│   │   ├── cleaner.py
│   │   └── chunker.py
│   │
│   └── utils/
│       ├── config.py
│       └── logger.py
│
├── scripts/
│   ├── ingest.py                  # 文档摄入入口
│   └── validate.py                # 质量校验入口
│
└── tests/
    ├── fixtures/
    ├── test_ingestion.py
    └── test_validator.py
```

Keep document ingestion, indexing, retrieval, and generation as separate modules.
Future stages (src/indexing/, src/retrieval/, src/llm/, src/rag/) will be added after the ingestion pipeline works.

## Architecture Rules

### Document ingestion

Document loading is organized under `src/ingestion/`.

`schema.py` defines the internal document structure that all loaders must return.

`registry.py` maps file extensions to the correct loader, so callers do not need to know which loader handles which format.

`pipeline.py` orchestrates batch ingestion: for each file in `data/raw/` or `data/interim/`, select the loader, extract text and metadata, and write the result to `data/processed/` as JSONL.

Loaders live in `src/ingestion/loaders/`. Each loader should return a consistent internal document structure.

At minimum, preserve:

* source file name
* source path
* document type
* page number or section when available
* extracted text
* extraction warnings

Do not return only plain strings when useful source metadata is available.

Legacy formats (DOC, PPT) are handled by `src/ingestion/converters/libreoffice.py`, which converts them to DOCX/PPTX before loading. Converted files are stored in `data/interim/`.

### Quality validation

After ingestion, records go through `src/preprocessing/validator.py` for quality gate.

Flow:

```text
data/processed/*.jsonl
        ↓ validate_record()
data/processed/success/*.jsonl      ← downstream consumers only read this
data/processed/failed/*.jsonl
```

Success criteria (all must hold):

* `text` exists, is not null, and `text.strip()` is non-empty
* `warnings` list is empty
* `source_file`, `source_path`, `doc_type`, `doc_id` all present and truthy

Optional fields (`page`, `section`, `metadata`) being null does NOT cause failure.

Success records gain `"status": "success"`.

Failed records gain:

```json
{
  "status": "failed",
  "failure_reasons": ["empty_text", "has_warnings", ...],
  "needs_ocr": true | false
}
```

`needs_ocr` is set to `true` when a PDF page has empty text or when a warning mentions OCR/image-based/scanned content. Otherwise it defaults to `false`.

Single malformed lines (e.g. bad JSON) must not abort the whole file. Parse errors are written to failed with `failure_reasons: ["parse_error"]`.

### Text preprocessing

Text cleaning and chunking must be separate operations.

Chunk metadata should include:

* document ID
* chunk ID
* source file
* page or section
* chunk position
* original metadata

Chunking parameters must be configurable rather than hard-coded.

### Indexing

Index construction must be separate from query-time retrieval.

The indexing module should support:

* building a new index
* persisting the index
* loading an existing index
* rebuilding the index
* avoiding accidental duplicate ingestion when possible

Do not place indexing logic directly inside the user-facing application.

### Retrieval

Retrieval should return both text and metadata.

Each retrieved result should contain:

* chunk content
* relevance score
* source file
* page or section when available
* chunk ID

The application must be able to display where an answer came from.

### LLM integration

DeepSeek API access must be isolated in the `src/llm/` package.

Do not:

* hard-code API keys
* commit secrets
* mix HTTP request code throughout the project
* silently ignore API errors

The API key must be read from an environment variable such as:

```env
DEEPSEEK_API_KEY=
```

### RAG pipeline

The RAG pipeline should orchestrate existing modules rather than duplicate their logic.

Expected flow:

```text
question
→ retrieve relevant chunks
→ construct grounded prompt
→ call DeepSeek
→ return answer and citations
```

The prompt should explicitly tell the model:

* retrieved documents may be unreliable
* do not treat source claims as automatically true
* distinguish source claims from general analysis
* mention uncertainty and conflicting claims
* cite the retrieved source passages
* flag manipulative, biased, pseudoscientific, or risky advice

## Content Reliability Rules

The knowledge base is not a verified source of relationship advice.

When working on answer generation or prompt design, preserve the following distinction:

1. What the retrieved source claims.
2. Whether the claim is supported or questionable.
3. What risks, bias, or uncertainty may exist.

Do not silently remove questionable source content during ingestion.

Instead, preserve it and allow later stages to attach labels such as:

* potentially biased
* unsupported claim
* pseudoscientific
* manipulative strategy
* safety risk
* conflicting advice
* source reliability unknown

The first MVP does not need a perfect automatic reliability classifier, but the architecture should not prevent adding one later.

## Coding Guidelines

* Use type hints for public functions.
* Keep functions focused on one responsibility.
* Prefer clear code over clever abstractions.
* Add docstrings to important modules and public functions.
* Use `pathlib.Path` instead of manually concatenating paths.
* Use Python logging rather than scattered `print` statements.
* Raise clear exceptions when an operation cannot continue.
* Do not suppress errors without recording the reason.
* Keep configuration outside business logic.
* Avoid global mutable state.
* Avoid adding large frameworks unless they clearly simplify the MVP.
* Do not add dependencies without explaining why they are needed.

## Agent Workflow

Before editing code:

1. Inspect the relevant files.
2. Identify the smallest set of files that needs to change.
3. State the intended implementation approach.
4. Check whether an existing abstraction already solves the problem.

When editing code:

1. Make the smallest reasonable change.
2. Do not refactor unrelated modules.
3. Preserve existing behavior unless the task explicitly changes it.
4. Add or update tests for meaningful behavior changes.
5. Keep public interfaces stable when possible.

After editing code:

1. Run relevant tests.
2. Run linting or formatting checks when configured.
3. Report which files changed.
4. Explain the important implementation decisions.
5. Report tests that passed or failed.
6. Never claim that a test was run when it was not run.

## Task Scope Rules

Do not implement multiple major stages in one change unless explicitly requested.

Prefer tasks such as:

* implement the TXT loader
* implement the DOCX loader
* define the internal document schema
* add configurable text chunking
* create the embedding interface
* build vector index persistence
* implement similarity retrieval
* add DeepSeek API client
* assemble the initial RAG pipeline

Avoid vague tasks such as:

* finish the entire RAG project
* optimize everything
* make it production ready

## Testing Expectations

Important modules should have unit tests.

At minimum, test:

* supported file loading
* unsupported file handling
* metadata preservation
* empty document handling
* chunk boundaries
* chunk overlap
* index save and load
* retrieval result structure
* missing API key behavior
* malformed configuration handling

Use small sample documents in `data/samples/` or test fixtures.

Tests must not depend on private dating materials stored in `data/raw/`.

External API calls should be mocked in unit tests whenever practical.

## Data and Git Rules

Never commit:

* `.env`
* API keys
* private documents
* purchased copyrighted documents
* generated vector indexes
* large processed datasets
* temporary extraction files
* local cache files

Only small, legally usable sample documents should be stored in the repository.

Expected `.gitignore` coverage includes:

```gitignore
.env
data/raw/*
data/processed/*
storage/*
__pycache__/
*.pyc
.pytest_cache/
.venv/
```

Keep placeholder files such as `.gitkeep` when empty directories must remain in Git.

## Configuration Rules

Configurable values may include:

* chunk size
* chunk overlap
* embedding model
* vector database path
* retrieval top-k
* DeepSeek model name
* temperature
* maximum context length
* logging level

Do not scatter these values across source files.

Secrets belong in environment variables. Non-secret application settings belong in configuration files.

## Documentation Rules

Update `README.md` when a change affects:

* installation
* environment setup
* supported formats
* project structure
* commands
* configuration
* user-facing behavior

New scripts should include a usage example.

## MVP Acceptance Criteria

The first demo is complete when a user can:

1. Put supported documents into a local data directory.
2. Run a command to process and index the documents.
3. Start a command-line or simple web interface.
4. Ask a question.
5. Receive a DeepSeek-generated answer based on retrieved passages.
6. See the source file and page or section for the retrieved evidence.
7. Receive a clear message when no relevant evidence is found.

Correctness, traceability, and understandable code are more important than advanced features during the MVP stage.

## Out of Scope for the Initial MVP

Do not implement these unless explicitly requested:

* image OCR pipelines
* video transcription
* audio transcription
* multimodal retrieval
* user authentication
* cloud deployment
* distributed processing
* complex agent systems
* automatic fine-tuning
* advanced knowledge graphs
* large-scale evaluation platforms
* fully automatic truth verification
