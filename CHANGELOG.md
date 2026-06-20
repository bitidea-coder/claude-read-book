# Changelog

## 0.3.0

Information-preserving compression rewrite. The 0.2.0 compressor dropped logical
connectives ("however", "therefore", "furthermore") as fluff — a real information
loss for technical/development books, where those words carry the reasoning. Fixed:

- **Connectives are remapped, never dropped:** `however`→`but`, `therefore`→`so`,
  `furthermore`→`also`. The logical relation survives in one token.
- **Negation is never touched** (`not`/`never`/`no`/`cannot`), and in safe mode
  **modality is preserved** (`you can use X` ≠ `use X`; `must`/`may`/`might` kept).
- **Two levels:** `--compress` (safe, near-lossless — the default) and
  `--compress-aggressive` (also collapses modal framing like `you should`/`there is`,
  for mild extra savings; negation still kept).
- Filler drop list narrowed to articles + pure intensifiers (`just`/`really`/`very`/
  `basically`…); epistemic hedges (`usually`/`often`/`typically`) are kept.
- Fixed leading-dot bug where space-before-punctuation cleanup ate the space in
  tokens like ` .env` / ` .locked`.
- SKILL.md now ranks token-saving levers by fidelity: **retrieval (lossless) first,
  LLM summarization second, `--compress` last (overflow only).** Documents the
  reality that dense technical reference compresses only ~4-5% — by design.

## 0.2.0

- Add `--compress`: deterministic caveman-style text compression (pure regex, no LLM,
  no token cost) for `--full` and `--chapter` output. Drops articles/filler/pleasantries/
  hedging/connective fluff; preserves code, inline code, URLs, file paths, numbers, and
  proper nouns. `--full --compress` reports the before/after token delta.

## 0.1.0

Initial release.

- `/read-book` skill + slash command.
- Extracts EPUB, PDF, HTML, Markdown, DOCX, and TXT via the `unstructured` library.
- Token-budgeted chunking with table-of-contents and page/section citations.
- Modes: index (default), `--search`, `--chapter N`, `--full`.
- PDF strategies: `fast`, `hi_res`, `ocr_only`, `auto`.
- Extraction cached as JSON keyed by file path for instant repeat queries.
- `setup.py` preflight (`--check` / `--json`) and idempotent installer (auto-downloads pandoc).
- SessionStart hook surfaces a one-line setup hint until dependencies are ready.
- Fully local — no network, no uploads, source file untouched.
