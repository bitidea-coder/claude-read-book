"""Token-aware chunking and table-of-contents building over extracted elements.

Takes the normalized element list from extract.py and produces:
  - chunks: contiguous runs of text capped at a token budget, each tagged with
    the page range and the nearest preceding heading (its "section")
  - toc: the list of detected headings/titles with their page + chunk index

Chunking respects element boundaries (never splits mid-element) and starts a
fresh chunk at every heading so a chunk maps cleanly to one section's prose.
"""

from __future__ import annotations

from typing import Any

# unstructured category names that act as section boundaries.
_HEADING_CATEGORIES = {"Title", "Header", "PageBreak"}

try:
    import tiktoken

    _ENC = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_ENC.encode(text))

except Exception:  # tiktoken missing or model data unavailable
    def count_tokens(text: str) -> int:
        # ~4 chars/token heuristic. Good enough for budgeting when tiktoken is absent.
        return max(1, len(text) // 4)


def _is_heading(element: dict[str, Any]) -> bool:
    if element.get("category") in _HEADING_CATEGORIES:
        return True
    # Short Title-cased lines that unstructured tagged as Title are headings;
    # also treat very short standalone lines as candidate headings.
    return element.get("category") == "Title" and len(element["text"]) < 120


def _page_range(pages: list[int | None]) -> tuple[int | None, int | None]:
    nums = [p for p in pages if p is not None]
    if not nums:
        return None, None
    return min(nums), max(nums)


def chunk_elements(
    elements: list[dict[str, Any]], max_tokens: int = 1200
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (chunks, toc).

    Each chunk: {index, section, page_start, page_end, tokens, text}
    Each toc entry: {title, page, chunk_index}
    """
    chunks: list[dict[str, Any]] = []
    toc: list[dict[str, Any]] = []

    cur_text: list[str] = []
    cur_pages: list[int | None] = []
    cur_tokens = 0
    cur_section = "(front matter)"

    def flush() -> None:
        nonlocal cur_text, cur_pages, cur_tokens
        if not cur_text:
            return
        ps, pe = _page_range(cur_pages)
        chunks.append(
            {
                "index": len(chunks),
                "section": cur_section,
                "page_start": ps,
                "page_end": pe,
                "tokens": cur_tokens,
                "text": "\n\n".join(cur_text),
            }
        )
        cur_text = []
        cur_pages = []
        cur_tokens = 0

    for el in elements:
        text = el["text"]
        is_head = _is_heading(el)

        if is_head:
            # Close the previous chunk; start a new section.
            flush()
            cur_section = text
            toc.append(
                {"title": text, "page": el.get("page"), "chunk_index": len(chunks)}
            )

        el_tokens = count_tokens(text)
        # If adding this element would blow the budget, flush first (keeps the
        # current section label for the continuation chunk).
        if cur_text and cur_tokens + el_tokens > max_tokens:
            flush()

        cur_text.append(text)
        cur_pages.append(el.get("page"))
        cur_tokens += el_tokens

    flush()
    return chunks, toc
