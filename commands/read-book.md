---
description: Read a book or document (EPUB, PDF, HTML, Markdown, DOCX, TXT). Extracts clean text with the unstructured library, chunks it with page/section citations, and searches or reads specific sections instead of dumping a whole book into context.
argument-hint: <book-path> [question]
allowed-tools: [Bash, Read, AskUserQuestion]
---

Invoke the `read-book` skill (defined in SKILL.md) with the user's arguments: $ARGUMENTS

Follow the skill's full pipeline: preflight setup check → extract text with unstructured → chunk into token-budgeted sections with a table of contents → search or read the relevant chunks → answer the user grounded in the extracted text, citing pages/sections. If the user provided no arguments, ask them for a book or document path before proceeding.
