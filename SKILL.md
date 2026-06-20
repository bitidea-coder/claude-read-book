---
name: read-book
description: Read a book or document (EPUB, PDF, HTML, Markdown, DOCX, TXT). Extracts clean text with the `unstructured` library, splits it into citable token-budgeted chunks with a table of contents, and lets Claude search or read specific sections instead of dumping a whole book into context. Use when the user points at a book/document file and wants it read, summarized, or queried.
argument-hint: "<book-path> [question]"
allowed-tools: Bash, Read, AskUserQuestion
license: MIT
user-invocable: true
---

# /read-book — Claude reads a book

Claude can already `Read` a PDF natively, but that breaks down on EPUBs (zipped
HTML), messy HTML, and large books that blow the context window. This skill fixes
that: a Python pipeline extracts clean text via the `unstructured` library, chunks
it with page/section citations, and hands Claude a table of contents — so Claude
pulls only the relevant sections instead of the whole book.

## Step 0 — Setup preflight (silent on success)

On **Windows** use `python`; on macOS/Linux use `python3`.

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/setup.py" --check
```

Exit 0 → say nothing, go to Step 1. Otherwise:

| Exit | Meaning | Action |
|------|---------|--------|
| `2` | `unstructured` not installed | Run installer |
| `3` | `pandoc` missing (EPUB needs it) | Run installer (auto-downloads pandoc) |

Installer (idempotent, heavy — pulls torch/onnx for PDF layout, ~3-5 GB first time):

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/setup.py"
```

`--json` gives `{unstructured, tiktoken, pandoc, tesseract, python, ready}`.
Within a session, skip Step 0 on follow-ups once `--check` returned 0.

## When to use

- User points at a `.epub`, `.pdf`, `.html`, `.md`, `.docx`, or `.txt` file and asks
  to read, summarize, or answer questions about it.
- User types `/read-book <path> [question]`.

## How to invoke

**Step 1 — parse input.** Separate the file path from any question.
`/read-book book.epub what does chapter 3 say about caching?`
→ path = `book.epub`, question = `what does chapter 3 say about caching?`

**Step 2 — extract + index.** Run with no mode flag first to get the TOC and chunk index:

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/read.py" "<path>"
```

This prints: source, chunk count, total tokens, a **table of contents**, and a
**chunk index** (one line per chunk with page range, token count, section, preview).
Extraction is cached in a temp dir keyed by file path — later `--search` / `--chapter`
calls are instant (no re-extraction).

PDF strategy (PDF only):
- `--pdf-strategy fast` (default) — text layer only, no ML, fast. Use for digital PDFs.
- `--pdf-strategy hi_res` — layout model; better tables/columns/figures. Slow.
- `--pdf-strategy ocr_only` — tesseract OCR. Use for scanned PDFs with no text layer.
- `--pdf-strategy auto` — let unstructured decide per page.

**Step 3 — choose how to read, by book size and the question:**

- **Small doc** (total tokens fit comfortably, say < ~15k) → dump it all:
  ```bash
  python "${CLAUDE_PLUGIN_ROOT}/scripts/read.py" "<path>" --full
  ```
- **Specific question** → search, then read the top hits:
  ```bash
  python "${CLAUDE_PLUGIN_ROOT}/scripts/read.py" "<path>" --search "your question"
  python "${CLAUDE_PLUGIN_ROOT}/scripts/read.py" "<path>" --chapter 12
  ```
  `--search` ranks chunks by term frequency (heading hits weighted higher) and prints
  a snippet per hit. `--chapter N` prints chunk N in full. Read the hits that matter,
  then answer.
- **Summarize the whole book** → walk the TOC, read chunks chapter by chapter with
  `--chapter N`, summarizing as you go. Don't `--full` a large book — it defeats the
  purpose and floods context.

**Step 4 — answer, citing pages/sections.** Every chunk carries a page range and its
section heading. Cite them (e.g. "§ Caching, p.41"). Ground claims in extracted text.

## Cutting tokens on big books

Two levers, use both:

1. **Don't read the whole book.** This is the main lever. Use `--search` + `--chapter`
   to pull only relevant chunks. For a summary, walk the TOC chapter by chapter and
   summarize as you go — never `--full` a large book.
2. **`--compress`** — caveman-compresses chunk text *deterministically* (pure regex,
   **no LLM, no token cost**) before it reaches context. Drops articles / filler /
   pleasantries / hedging / connective fluff; preserves code, inline `code`, URLs,
   file paths, commands, numbers, and proper nouns exactly. Works with `--full` and
   `--chapter`.
   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/read.py" "<path>" --chapter 12 --compress
   python "${CLAUDE_PLUGIN_ROOT}/scripts/read.py" "<path>" --full --compress
   ```
   Savings depend on the prose: verbose writing shrinks ~20-30%; dense technical
   reference (lots of terms/commands/proper nouns, all preserved) shrinks less (~5%).
   `--full --compress` prints the before/after token delta. Compression is lossy on
   grammar but never on technical substance — for exact-quote work, read without it.

## Tuning

- `--max-tokens N` — chunk size (default 1200). Lower for finer-grained search/citations.
- `--out-dir DIR` — persist the cache somewhere instead of temp (good for re-querying a
  book across sessions).
- `--top-n N` — number of search hits (default 5).
- `--json` — machine-readable output for any mode.

## Token efficiency

The whole point: never paste a full book into context. Extraction + TOC is cheap (a few
hundred tokens). Searching is cheap. Only the chunks you `--chapter` into cost real
tokens. For a 300-page book, reading 3-4 relevant chunks beats dumping 150k tokens.

If you already extracted a book this session, the cache persists — re-run `--search` /
`--chapter` freely without re-extracting.

## What this skill does / does NOT do

**Does:** runs `unstructured` locally to parse the file; writes extracted chunks + TOC as
JSON to a temp cache dir; reads only the file you point at.

**Does NOT:** send the book to any API (all extraction is local — no network, no embeddings);
modify the source file; persist anything outside the cache dir.

**Bundled scripts:** `scripts/read.py` (entry), `scripts/extract.py` (unstructured router),
`scripts/chunk.py` (token chunking + TOC), `scripts/search.py` (keyword search),
`scripts/caveman.py` (deterministic `--compress` text shrink), `scripts/setup.py` (preflight + installer).

Review scripts before first use to verify behavior.
