# Data Processing Pitfalls

This note records data-layer issues observed in the current ingestion,
validation, and processed JSONL outputs. It intentionally excludes WSL,
permissions, Git, dependency installation, and other environment problems.

## Empty Text Must Fail

Records whose `text` is `null`, empty, or only whitespace must not enter later
pipeline stages. The validator currently marks these records with reasons such
as `null_text` or `empty_text`.

Real failed PDF records include empty `text` values, for example scanned pages
that produced no extractable text.

## Warnings Block Downstream Use

Any non-empty `warnings` list makes a record fail validation. The warning text
must be preserved because it explains the extraction problem, such as image-only
PDF pages or encoding fallback issues.

Downstream cleaning, chunking, embedding, and indexing should not consume
records with warnings.

## Optional Null Fields Are Valid

`title: null`, `section: null`, and `page: null` are valid metadata states.
They are common in the current success records and must not be treated as
validation failures. Only required fields such as `source_file`, `source_path`,
`doc_type`, and `doc_id` are mandatory.

## Scanned PDFs Need OCR Later

Some PDFs parse as empty text because the page content is image-based or
scanned. These records should fail validation and set `needs_ocr: true` when
the PDF text is empty or the warning mentions OCR, image-based, or scanned
content.

The current MVP records the need for OCR but does not implement OCR.

## Success Directory Is the Downstream Boundary

Later stages must read only from `data/processed/success/`. The
`data/processed/failed/` directory is for diagnostics, repair, OCR targeting,
or reprocessing, not for chunking, embedding, retrieval, or indexing.

## Avoid Inventing Data Problems

When adding new preprocessing rules, prefer evidence from:

- `src/preprocessing/validator.py`
- existing validator tests
- actual records under `data/processed/success/`
- actual records under `data/processed/failed/`

Do not add speculative filters that silently remove source content. Preserve
questionable content for later reliability labeling rather than dropping it at
the data cleaning stage.
