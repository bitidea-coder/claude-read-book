"""Keyword search over chunked book text.

Ranks chunks by term-frequency of the query terms, with a small bonus when a
term appears in the chunk's section heading. Returns the top-N chunks with a
short context snippet around the best match so Claude can decide what to read
in full. No embeddings / no network — pure local scoring.
"""

from __future__ import annotations

import re
from typing import Any

_WORD = re.compile(r"\w+", re.UNICODE)


def _terms(query: str) -> list[str]:
    return [t.lower() for t in _WORD.findall(query) if len(t) > 1]


def _snippet(text: str, terms: list[str], width: int = 240) -> str:
    low = text.lower()
    pos = -1
    for t in terms:
        pos = low.find(t)
        if pos != -1:
            break
    if pos == -1:
        return text[:width].strip()
    start = max(0, pos - width // 2)
    end = min(len(text), pos + width // 2)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[start:end].strip()}{suffix}"


def search(
    chunks: list[dict[str, Any]], query: str, top_n: int = 5
) -> list[dict[str, Any]]:
    terms = _terms(query)
    if not terms:
        return []

    scored: list[tuple[float, dict[str, Any]]] = []
    for ch in chunks:
        body = ch["text"].lower()
        section = (ch.get("section") or "").lower()
        score = 0.0
        for t in terms:
            score += body.count(t)
            score += 3.0 * section.count(t)  # heading hits weigh more
        if score > 0:
            scored.append((score, ch))

    scored.sort(key=lambda x: x[0], reverse=True)
    results = []
    for score, ch in scored[:top_n]:
        results.append(
            {
                "chunk_index": ch["index"],
                "section": ch.get("section"),
                "page_start": ch.get("page_start"),
                "page_end": ch.get("page_end"),
                "score": score,
                "tokens": ch.get("tokens"),
                "snippet": _snippet(ch["text"], terms),
            }
        )
    return results
