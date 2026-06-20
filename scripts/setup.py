"""read-book preflight + installer.

  python setup.py --check   exit 0 if ready, non-zero with a reason otherwise
  python setup.py           install missing pieces (idempotent)
  python setup.py --json    machine-readable status

Checks:
  - core import: `unstructured`
  - tiktoken (chunk budgeting; optional, falls back to heuristic)
  - pandoc (epub partitioning needs it; auto-downloaded via pypandoc if missing)
  - tesseract (only needed for scanned-PDF OCR; reported, not required)

Exit codes (--check):
  0 ready · 2 unstructured missing · 3 pandoc missing (epub will fail)
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys


def _have_module(name: str) -> bool:
    try:
        __import__(name)
        return True
    except Exception:
        return False


def _have_pandoc() -> bool:
    if shutil.which("pandoc"):
        return True
    try:
        import pypandoc

        pypandoc.get_pandoc_path()
        return True
    except Exception:
        return False


def status() -> dict:
    return {
        "unstructured": _have_module("unstructured"),
        "tiktoken": _have_module("tiktoken"),
        "docx": _have_module("docx"),  # python-docx, for .docx route
        "markdown": _have_module("markdown"),  # for .md route
        "pandoc": _have_pandoc(),
        "tesseract": bool(shutil.which("tesseract")),
        "python": sys.version.split()[0],
    }


def _check(s: dict) -> int:
    if not s["unstructured"]:
        return 2
    if not s["pandoc"]:
        return 3
    return 0


def install() -> None:
    print("[read-book] installing unstructured[epub,pdf,html] + tiktoken …")
    subprocess.run(
        [
            sys.executable, "-m", "pip", "install",
            "unstructured[epub,pdf,html]",
            "tiktoken",
            "python-docx",  # .docx route
            "markdown",     # .md route
        ],
        check=True,
    )
    if not _have_pandoc():
        print("[read-book] fetching pandoc via pypandoc …")
        try:
            import pypandoc

            pypandoc.download_pandoc()
        except Exception as e:
            print(
                f"[read-book] could not auto-download pandoc: {e}\n"
                "  Install manually: https://pandoc.org/installing.html "
                "(epub support needs it).",
                file=sys.stderr,
            )
    if not shutil.which("tesseract"):
        print(
            "[read-book] NOTE: tesseract not found. Only needed for scanned-PDF OCR "
            "(--pdf-strategy ocr_only/hi_res). Install: https://github.com/UB-Mannheim/tesseract/wiki",
            file=sys.stderr,
        )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    s = status()

    if args.json:
        out = dict(s)
        out["ready"] = _check(s) == 0
        print(json.dumps(out, indent=2))
        return 0

    if args.check:
        code = _check(s)
        if code == 2:
            print("[read-book] unstructured not installed. Run: python scripts/setup.py", file=sys.stderr)
        elif code == 3:
            print("[read-book] pandoc missing — epub extraction will fail. Run: python scripts/setup.py", file=sys.stderr)
        return code

    install()
    print("[read-book] done.", file=sys.stderr if _check(status()) else sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
