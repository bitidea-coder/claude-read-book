"""read-book entry point.

Extract a book (epub/pdf/html/md/docx/txt) into chunked, citable text and
print a report for Claude. Three modes:

  default            extract + print TOC + chunk index (no full bodies)
  --full             also print every chunk's full text (small books only)
  --search "query"   print the top matching chunks with snippets
  --chapter N        print the full text of chunk index N (and a few around it)

Chunks and TOC are cached as JSON in --out-dir so repeated --search / --chapter
calls don't re-extract (re-extraction of a big PDF with hi_res is slow).

Usage:
  python read.py BOOK [--pdf-strategy fast|hi_res|ocr_only|auto]
                      [--max-tokens N] [--out-dir DIR]
                      [--full | --search QUERY | --chapter N]
                      [--json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile

import caveman as caveman_mod
import chunk as chunk_mod
import extract as extract_mod
import search as search_mod


def _maybe_compress(chunks, enabled):
    """Return (chunks, stats|None). When enabled, caveman-compress every chunk's
    text deterministically (no LLM) and recount tokens with the same tokenizer."""
    if not enabled:
        return chunks, None
    return caveman_mod.compress_chunks(chunks, chunk_mod.count_tokens)


def _cache_dir(path: str, out_dir: str | None) -> str:
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        return out_dir
    key = hashlib.sha1(os.path.abspath(path).encode()).hexdigest()[:12]
    d = os.path.join(tempfile.gettempdir(), f"read-book-{key}")
    os.makedirs(d, exist_ok=True)
    return d


def _load_or_build(path: str, pdf_strategy: str, max_tokens: int, cache: str):
    chunks_f = os.path.join(cache, "chunks.json")
    toc_f = os.path.join(cache, "toc.json")
    meta_f = os.path.join(cache, "meta.json")

    if os.path.isfile(chunks_f) and os.path.isfile(toc_f):
        with open(chunks_f, encoding="utf-8") as f:
            chunks = json.load(f)
        with open(toc_f, encoding="utf-8") as f:
            toc = json.load(f)
        return chunks, toc

    elements = extract_mod.extract(path, pdf_strategy=pdf_strategy)
    chunks, toc = chunk_mod.chunk_elements(elements, max_tokens=max_tokens)

    with open(chunks_f, "w", encoding="utf-8") as f:
        json.dump(chunks, f, ensure_ascii=False)
    with open(toc_f, "w", encoding="utf-8") as f:
        json.dump(toc, f, ensure_ascii=False)
    with open(meta_f, "w", encoding="utf-8") as f:
        json.dump(
            {
                "source": os.path.abspath(path),
                "elements": len(elements),
                "chunks": len(chunks),
                "total_tokens": sum(c["tokens"] for c in chunks),
                "pdf_strategy": pdf_strategy,
            },
            f,
            ensure_ascii=False,
        )
    return chunks, toc


def _print_report(path, chunks, toc, cache):
    total_tokens = sum(c["tokens"] for c in chunks)
    print("# read-book: extraction report\n")
    print(f"- **Source:** {os.path.basename(path)}")
    print(f"- **Chunks:** {len(chunks)}  |  **Total tokens:** ~{total_tokens:,}")
    print(f"- **Cache:** `{cache}`\n")

    print("## Table of contents\n")
    if toc:
        for entry in toc:
            pg = f" (p.{entry['page']})" if entry.get("page") else ""
            print(f"- [chunk {entry['chunk_index']}]{pg} {entry['title']}")
    else:
        print("_No headings detected — flat document._")

    print("\n## Chunk index\n")
    for c in chunks:
        pr = ""
        if c.get("page_start") is not None:
            pr = (
                f" p.{c['page_start']}"
                if c["page_start"] == c["page_end"]
                else f" p.{c['page_start']}-{c['page_end']}"
            )
        head = c["text"][:80].replace("\n", " ")
        print(f"- chunk {c['index']}{pr} · {c['tokens']}tok · «{c['section'][:40]}» — {head}…")

    print(
        "\n_Next: `--search \"your question\"` to find sections, "
        "or `--chapter N` to read chunk N in full._"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="Extract and read a book for Claude.")
    ap.add_argument("book", help="Path to epub/pdf/html/md/docx/txt")
    ap.add_argument(
        "--pdf-strategy",
        default="fast",
        choices=["fast", "hi_res", "ocr_only", "auto"],
        help="PDF extraction strategy (default: fast = text layer, no ML)",
    )
    ap.add_argument("--max-tokens", type=int, default=1200, help="Max tokens per chunk")
    ap.add_argument("--out-dir", default=None, help="Cache dir (default: temp)")
    ap.add_argument("--full", action="store_true", help="Print every chunk's full text")
    ap.add_argument("--search", metavar="QUERY", help="Search chunks, print top matches")
    ap.add_argument("--chapter", type=int, metavar="N", help="Print full text of chunk N")
    ap.add_argument("--top-n", type=int, default=5, help="Results for --search")
    ap.add_argument(
        "--compress",
        action="store_true",
        help="Caveman-compress chunk text (deterministic, no LLM) to cut tokens "
        "on --full / --chapter output. Preserves code, URLs, paths, numbers.",
    )
    ap.add_argument("--json", action="store_true", help="Emit JSON instead of markdown")
    args = ap.parse_args()

    try:
        cache = _cache_dir(args.book, args.out_dir)
        chunks, toc = _load_or_build(
            args.book, args.pdf_strategy, args.max_tokens, cache
        )
    except (FileNotFoundError, ValueError) as e:
        print(f"[read-book] ERROR: {e}", file=sys.stderr)
        return 1
    except ImportError as e:
        print(
            f"[read-book] ERROR: missing dependency: {e}\n"
            "Run: python scripts/setup.py",
            file=sys.stderr,
        )
        return 2

    if args.search:
        results = search_mod.search(chunks, args.search, top_n=args.top_n)
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
            return 0
        print(f"# Search: «{args.search}» — {len(results)} hits\n")
        for r in results:
            pr = f"p.{r['page_start']}-{r['page_end']}" if r.get("page_start") else "?"
            print(f"## chunk {r['chunk_index']} · {pr} · score {r['score']:.0f}")
            print(f"_section: {r['section']}_\n")
            print(f"> {r['snippet']}\n")
        print("_Read a full hit with `--chapter N`._")
        return 0

    if args.chapter is not None:
        n = args.chapter
        if not (0 <= n < len(chunks)):
            print(f"[read-book] ERROR: chunk {n} out of range 0-{len(chunks)-1}", file=sys.stderr)
            return 1
        c = dict(chunks[n])
        if args.compress:
            c["text"] = caveman_mod.compress_text(c["text"])
        if args.json:
            print(json.dumps(c, ensure_ascii=False, indent=2))
            return 0
        pr = f"p.{c['page_start']}-{c['page_end']}" if c.get("page_start") else "?"
        cc = " · caveman" if args.compress else ""
        print(f"# chunk {n} · {pr} · «{c['section']}»{cc}\n")
        print(c["text"])
        return 0

    if args.json:
        print(json.dumps({"chunks": chunks, "toc": toc, "cache": cache}, ensure_ascii=False, indent=2))
        return 0

    _print_report(args.book, chunks, toc, cache)
    if args.full:
        body, stats = _maybe_compress(chunks, args.compress)
        if stats:
            print(
                f"\n_Caveman-compressed: ~{stats['tokens_before']:,} → "
                f"~{stats['tokens_after']:,} tokens "
                f"(−{stats['percent_saved']}%). Code/URLs/paths preserved._"
            )
        print("\n---\n## Full text\n")
        for c in body:
            print(f"\n### chunk {c['index']} «{c['section']}»\n")
            print(c["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
