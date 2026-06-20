"""Deterministic caveman-style text compression — no LLM, no network.

Ports the caveman-compress rule set (drop articles / filler / pleasantries /
hedging / connective fluff, collapse redundant phrasing) into pure regex so a
whole book can be shrunk locally at zero token cost before any chunk reaches
Claude's context.

Protected spans are never touched: fenced code blocks, inline `code`, URLs,
and bare file paths. Everything else is natural-language prose and fair game.

Typical shrink on technical prose: ~20-35% tokens. Lossy by design (drops
grammatical filler) but preserves all technical substance, numbers, names,
code, and links.
"""

from __future__ import annotations

import re

# ---- protected spans: extracted, replaced with sentinels, restored verbatim ----

_FENCED = re.compile(r"```.*?```", re.DOTALL)
_INLINE = re.compile(r"`[^`]+`")
_URL = re.compile(r"https?://\S+")
# Bare paths like ./foo/bar.py, /usr/local/bin, src/components/x.ts
_PATH = re.compile(r"(?:\.{0,2}/)?(?:[\w.-]+/)+[\w.-]+")

_SENTINEL = "\x00PROT{}\x00"


def _protect(text: str) -> tuple[str, list[str]]:
    spans: list[str] = []

    def stash(m: re.Match) -> str:
        spans.append(m.group(0))
        return _SENTINEL.format(len(spans) - 1)

    for pat in (_FENCED, _INLINE, _URL, _PATH):
        text = pat.sub(stash, text)
    return text, spans


def _restore(text: str, spans: list[str]) -> str:
    for i, s in enumerate(spans):
        text = text.replace(_SENTINEL.format(i), s)
    return text


# ---- word/phrase rules (case-insensitive, word-boundary safe) ----

# Whole words to delete outright.
_DROP_WORDS = [
    # articles
    "a", "an", "the",
    # filler / intensifiers
    "just", "really", "basically", "actually", "simply", "essentially",
    "generally", "very", "quite", "rather", "somewhat", "fairly",
    "literally", "truly", "indeed", "certainly", "definitely",
    # connective fluff
    "however", "furthermore", "additionally", "moreover", "nonetheless",
    "nevertheless", "thus", "therefore", "hence", "accordingly",
]

# Multi-word phrases collapsed to a shorter form (or dropped if "").
_PHRASES = [
    (r"in order to", "to"),
    (r"make sure to", ""),
    (r"make sure that", "ensure"),
    (r"be sure to", ""),
    (r"the reason is because", "because"),
    (r"the reason why", "why"),
    (r"due to the fact that", "because"),
    (r"in spite of the fact that", "although"),
    (r"with regard to", "re"),
    (r"with respect to", "re"),
    (r"in terms of", "in"),
    (r"a number of", "several"),
    (r"a large number of", "many"),
    (r"the majority of", "most"),
    (r"at this point in time", "now"),
    (r"in the event that", "if"),
    (r"it is important to note that", ""),
    (r"it is worth noting that", ""),
    (r"it should be noted that", ""),
    (r"you should", ""),
    (r"you need to", ""),
    (r"you can", ""),
    (r"you will", ""),
    (r"there is", ""),
    (r"there are", ""),
    (r"it is", ""),
    # single-word verbose -> short synonym
    (r"utilize", "use"),
    (r"utilizes", "uses"),
    (r"utilizing", "using"),
    (r"leverage", "use"),
    (r"approximately", "~"),
    (r"in addition", ""),
    (r"as well as", "and"),
    (r"such as", "like"),
    (r"in conclusion", ""),
    (r"for example", "e.g."),
    (r"for instance", "e.g."),
    (r"that is to say", "i.e."),
]

_DROP_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in _DROP_WORDS) + r")\b",
    re.IGNORECASE,
)
_PHRASE_RES = [
    (re.compile(r"\b" + pat + r"\b", re.IGNORECASE), repl) for pat, repl in _PHRASES
]

_WS = re.compile(r"[ \t]{2,}")
# Collapse space before sentence punctuation. Period/comma only when followed
# by whitespace or end-of-string, so leading-dot tokens (".locked", ".env") and
# decimals ("3 .14" never occurs but be safe) keep their preceding space.
_SPACE_PUNCT = re.compile(r"\s+([;:!?])|\s+([,.])(?=\s|$)")
_MULTI_NL = re.compile(r"\n{3,}")


def _fix_space_punct(m: re.Match) -> str:
    return (m.group(1) or m.group(2))


def compress_text(text: str) -> str:
    """Compress prose. Protected code/URLs/paths pass through verbatim."""
    text, spans = _protect(text)

    # Phrases first (some contain words we'd otherwise drop).
    for rx, repl in _PHRASE_RES:
        text = rx.sub(repl, text)

    text = _DROP_RE.sub("", text)

    # Tidy whitespace the deletions left behind.
    text = _WS.sub(" ", text)
    text = _SPACE_PUNCT.sub(_fix_space_punct, text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = _MULTI_NL.sub("\n\n", text)
    # Drop spaces at line starts created by leading-word deletion.
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"^[ \t]+", "", text)

    text = _restore(text, spans)
    return text.strip()


def compress_chunks(chunks: list[dict], count_tokens) -> tuple[list[dict], dict]:
    """Compress every chunk's text in place (new list), recount tokens.

    Returns (new_chunks, stats) where stats has before/after token totals.
    `count_tokens` is injected to reuse the same tokenizer as chunk.py.
    """
    before = sum(c.get("tokens", 0) for c in chunks)
    out = []
    after = 0
    for c in chunks:
        ctext = compress_text(c["text"])
        toks = count_tokens(ctext)
        after += toks
        nc = dict(c)
        nc["text"] = ctext
        nc["tokens"] = toks
        nc["compressed"] = True
        out.append(nc)
    saved = before - after
    pct = (saved / before * 100) if before else 0.0
    return out, {
        "tokens_before": before,
        "tokens_after": after,
        "tokens_saved": saved,
        "percent_saved": round(pct, 1),
    }
