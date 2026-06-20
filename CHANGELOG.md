# Changelog

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
