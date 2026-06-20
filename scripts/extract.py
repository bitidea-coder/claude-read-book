"""Extract structured text from a book file using the `unstructured` library.

Routes a single file (epub / pdf / html / md / docx / txt) through
unstructured's partitioner and returns a flat list of normalized elements:

    {"type": str, "text": str, "page": int | None, "category": str}

unstructured does the format detection and heavy lifting. This module only
normalizes its output into a shape the rest of the pipeline can chunk and cite.
"""

from __future__ import annotations

import os
from typing import Any

# Map of file extension -> the unstructured partitioner to prefer. unstructured
# also has a generic `partition` that auto-detects, but importing the specific
# partitioner keeps the dependency surface (and failure modes) explicit.
_EXT_ROUTES = {
    ".epub": "epub",
    ".pdf": "pdf",
    ".html": "html",
    ".htm": "html",
    ".md": "md",
    ".markdown": "md",
    ".docx": "docx",
    ".txt": "text",
    ".text": "text",
}


def supported_extensions() -> list[str]:
    return sorted(_EXT_ROUTES.keys())


def detect_kind(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    kind = _EXT_ROUTES.get(ext)
    if kind is None:
        raise ValueError(
            f"Unsupported file type {ext!r}. Supported: {', '.join(supported_extensions())}"
        )
    return kind


def _partition(path: str, kind: str, pdf_strategy: str) -> list[Any]:
    """Call the matching unstructured partitioner. Imports are local so a missing
    optional dependency only breaks the format that needs it, not the whole CLI."""
    if kind == "epub":
        from unstructured.partition.epub import partition_epub

        return partition_epub(filename=path)
    if kind == "pdf":
        from unstructured.partition.pdf import partition_pdf

        # strategy: "fast" (text layer only, no ML), "hi_res" (layout model),
        # "ocr_only" (tesseract). "auto" lets unstructured decide per-page.
        return partition_pdf(filename=path, strategy=pdf_strategy)
    if kind == "html":
        from unstructured.partition.html import partition_html

        return partition_html(filename=path)
    if kind == "md":
        from unstructured.partition.md import partition_md

        return partition_md(filename=path)
    if kind == "docx":
        from unstructured.partition.docx import partition_docx

        return partition_docx(filename=path)
    if kind == "text":
        from unstructured.partition.text import partition_text

        return partition_text(filename=path)
    raise ValueError(f"No partitioner for kind {kind!r}")


def _page_of(element: Any) -> int | None:
    meta = getattr(element, "metadata", None)
    if meta is None:
        return None
    return getattr(meta, "page_number", None)


def extract(path: str, pdf_strategy: str = "fast") -> list[dict[str, Any]]:
    """Extract a normalized element list from `path`.

    pdf_strategy only applies to PDFs; ignored for other formats.
    Raises ValueError on unsupported extension, FileNotFoundError if missing.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"No such file: {path}")

    kind = detect_kind(path)
    raw = _partition(path, kind, pdf_strategy)

    elements: list[dict[str, Any]] = []
    for el in raw:
        text = (getattr(el, "text", "") or "").strip()
        if not text:
            continue
        elements.append(
            {
                "type": type(el).__name__,
                "category": getattr(el, "category", type(el).__name__),
                "text": text,
                "page": _page_of(el),
            }
        )
    return elements
