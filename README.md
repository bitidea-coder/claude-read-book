# claude-read-book

**Give Claude a book input.** Claude can read a PDF natively, but chokes on EPUBs (zipped HTML), messy HTML, and large books that blow the context window. `/read-book` fixes that: a Python pipeline extracts clean text with the [`unstructured`](https://github.com/Unstructured-IO/unstructured) library, splits it into citable token-budgeted chunks with a table of contents, and lets Claude **search or read specific sections** instead of dumping a whole book into context.

Supports **EPUB, PDF, HTML, Markdown, DOCX, and TXT**.

> Inspired by [`claude-video`](https://github.com/bradautomates/claude-video) (`/watch`) — same idea, applied to books and documents.

## Install

```
/plugin marketplace add bitidea-coder/claude-read-book
/plugin install read-book@claude-read-book
/reload-plugins
```

Then run the one-time dependency installer (the SessionStart hook will remind you if it's missing):

```bash
# macOS / Linux
python3 ~/.claude/plugins/cache/claude-read-book/read-book/*/scripts/setup.py
# Windows
python  %USERPROFILE%\.claude\plugins\cache\claude-read-book\read-book\*\scripts\setup.py
```

This installs `unstructured[epub,pdf,html]`, `tiktoken`, `python-docx`, `markdown`, and auto-downloads `pandoc` (required for EPUB). First install is heavy (~3–5 GB) because the PDF layout models pull in `torch`/`onnx`. `tesseract` is optional — only needed for OCR on scanned PDFs.

## Usage

```
/read-book mybook.epub
/read-book mybook.epub what does it say about caching?
/read-book report.pdf --pdf-strategy hi_res
```

Or call the script directly:

```bash
python scripts/read.py BOOK                   # extract → table of contents + chunk index
python scripts/read.py BOOK --search "query"  # rank chunks, print snippets
python scripts/read.py BOOK --chapter N        # print chunk N in full
python scripts/read.py BOOK --full             # dump everything (small docs only)
```

### PDF strategies

| Strategy | Use for | Cost |
|----------|---------|------|
| `fast` (default) | digital PDFs with a text layer | fast, no ML |
| `hi_res` | complex layouts, tables, columns | slow, uses layout model |
| `ocr_only` | scanned PDFs (images, no text) | needs `tesseract` |
| `auto` | let unstructured decide per page | varies |

## How it works

1. **Extract** — `unstructured` partitions the file into typed elements (titles, paragraphs, etc.) with page numbers.
2. **Chunk** — elements are grouped into token-budgeted chunks (default 1200 tokens), split at section headings, each tagged with a page range and its section.
3. **Index** — a table of contents and chunk index are printed; the extraction is cached as JSON in a temp dir keyed by file path, so repeat queries are instant.
4. **Search / read** — Claude searches chunks (keyword ranking, heading-weighted) and reads only the relevant ones, citing pages and sections.

The point: **never paste a whole book into context.** For a 300-page book, reading 3–4 relevant chunks beats dumping 150k tokens.

## Privacy

Everything runs **locally** — no network calls, no embeddings API, nothing uploaded. The source file is never modified. Extracted chunks are cached under the system temp dir (or `--out-dir`).

## Scripts

| File | Role |
|------|------|
| `scripts/read.py` | entry point — extract, index, `--search`, `--chapter`, `--full` |
| `scripts/extract.py` | routes a file to the right `unstructured` partitioner |
| `scripts/chunk.py` | token-budget chunking + table-of-contents building |
| `scripts/search.py` | keyword search with heading-weighted ranking |
| `scripts/setup.py` | preflight `--check` and dependency installer |

Review the scripts before first use to verify behavior.

## License

MIT
