"""Deterministic caveman-style text compression — no LLM, no network.

Shrinks prose locally (zero token cost) before chunks reach Claude's context.
Designed around one rule: **never drop information, only redundancy.**

What that means concretely:
  - Articles + pure filler (just/really/very/…) are dropped — zero propositional
    content, the model reconstructs them for free.
  - Logical connectives are NEVER dropped — they encode reasoning. Instead they
    are remapped to a 1-token synonym that keeps the relation:
        however/nevertheless → but   (contrast preserved)
        therefore/thus/hence → so    (cause preserved)
        furthermore/moreover → also  (addition preserved)
  - Negation (not/never/no/cannot/…) is NEVER touched.
  - Modality (you can/should/may/might/must) is preserved in `safe` mode, because
    "you can use Redis" (option) ≠ "use Redis" (command).
  - Code, inline `code`, URLs, and file paths are protected verbatim.

Two levels:
  safe        (default) near-lossless: meaning identical, ~5-15% on prose.
  aggressive  (opt-in)  also collapses modal framing (you should → imperative,
              there is/it is → drop). Higher %, accepts mild meaning shift.

Compression is a LAST resort for overflow — retrieval (--search/--chapter) is the
real token lever and is lossless. See SKILL.md.
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


# ---- logical connectives: REMAP, never drop (preserves reasoning) ----
# Applied in BOTH tiers. Replacement keeps the logical relation in 1 token.

_CONNECTIVES = {
    "however": "but",
    "nevertheless": "but",
    "nonetheless": "but",
    "conversely": "but",
    "therefore": "so",
    "thus": "so",
    "hence": "so",
    "consequently": "so",
    "accordingly": "so",
    "furthermore": "also",
    "moreover": "also",
    "additionally": "also",
}
_CONNECTIVE_RE = re.compile(
    r"\b(" + "|".join(_CONNECTIVES) + r")\b", re.IGNORECASE
)


def _remap_connective(m: re.Match) -> str:
    return _CONNECTIVES[m.group(1).lower()]


# ---- pure filler: safe to drop in BOTH tiers (no propositional content) ----
# NOTE: deliberately EXCLUDES hedges that carry epistemic info
# (generally, usually, often, typically, roughly, somewhat, arguably, relatively)
# and EXCLUDES negation and modality. Those change meaning.

_DROP_WORDS = [
    "a", "an", "the",          # articles
    "just", "really", "actually", "simply", "basically",
    "literally", "truly", "indeed", "very", "quite",
    "certainly", "definitely",
]
_DROP_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in _DROP_WORDS) + r")\b",
    re.IGNORECASE,
)

# ---- verbose phrases -> short equivalent: meaning-preserving, BOTH tiers ----
# Concessive/conditional collapses keep the logic word (although/if/because).

_PHRASES_SAFE = [
    (r"in spite of the fact that", "although"),
    (r"despite the fact that", "although"),
    (r"due to the fact that", "because"),
    (r"the reason is because", "because"),
    (r"in the event that", "if"),
    (r"at this point in time", "now"),
    (r"a large number of", "many"),
    (r"a number of", "several"),
    (r"the majority of", "most"),
    (r"with regard to", "about"),
    (r"with respect to", "about"),
    (r"the reason why", "why"),
    (r"in order to", "to"),
    (r"for example", "e.g."),
    (r"for instance", "e.g."),
    (r"that is to say", "i.e."),
    (r"as well as", "and"),
    (r"such as", "like"),
    (r"make sure that", "ensure"),
    (r"make sure to", ""),
    (r"be sure to", ""),
    (r"it is important to note that", ""),
    (r"it is worth noting that", ""),
    (r"it should be noted that", ""),
    (r"utilizes", "uses"),
    (r"utilizing", "using"),
    (r"utilize", "use"),
    (r"approximately", "~"),
    (r"in addition", "also"),
]

# ---- aggressive-only: collapses modal framing. Opt-in, mild meaning shift. ----
# Excludes "you must" / "you may" / "you might" (necessity & possibility = info).

_PHRASES_AGGRESSIVE = [
    (r"you may want to", ""),
    (r"you might want to", ""),
    (r"you need to", ""),
    (r"you have to", ""),
    (r"you should", ""),
    (r"you can", ""),
    (r"you will", ""),
    (r"there is", ""),
    (r"there are", ""),
    (r"there's", ""),
    (r"it is", ""),
]


def _compile_phrases(pairs):
    # Longest pattern first so specific multi-word phrases win over substrings.
    pairs = sorted(pairs, key=lambda p: len(p[0]), reverse=True)
    return [(re.compile(r"\b" + pat + r"\b", re.IGNORECASE), repl) for pat, repl in pairs]


_SAFE_RES = _compile_phrases(_PHRASES_SAFE)
_AGG_RES = _compile_phrases(_PHRASES_AGGRESSIVE)

# ---- whitespace tidy ----

_WS = re.compile(r"[ \t]{2,}")
# Collapse space before sentence punctuation, but only for ,/. when followed by
# whitespace/EOL so leading-dot tokens (".locked", ".env") keep their space.
_SPACE_PUNCT = re.compile(r"\s+([;:!?])|\s+([,.])(?=\s|$)")
_MULTI_NL = re.compile(r"\n{3,}")


def _fix_space_punct(m: re.Match) -> str:
    return m.group(1) or m.group(2)


def compress_text(text: str, level: str = "safe") -> str:
    """Compress prose. level: 'safe' (near-lossless) or 'aggressive'.

    Protected code/URLs/paths pass through verbatim. Negation and (in safe mode)
    modality are never altered. Logical connectives are remapped, never dropped.
    """
    if level not in ("safe", "aggressive"):
        raise ValueError(f"level must be 'safe' or 'aggressive', got {level!r}")

    text, spans = _protect(text)

    # 1. Remap connectives (both tiers) — preserve logic before any drop.
    text = _CONNECTIVE_RE.sub(_remap_connective, text)

    # 2. Phrase collapses (safe set always; aggressive set adds modal framing).
    for rx, repl in _SAFE_RES:
        text = rx.sub(repl, text)
    if level == "aggressive":
        for rx, repl in _AGG_RES:
            text = rx.sub(repl, text)

    # 3. Drop pure filler words (both tiers).
    text = _DROP_RE.sub("", text)

    # 4. Tidy whitespace the deletions left behind.
    text = _WS.sub(" ", text)
    text = _SPACE_PUNCT.sub(_fix_space_punct, text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = _MULTI_NL.sub("\n\n", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"^[ \t]+", "", text)
    # NOTE: deliberately do NOT auto-recapitalize sentence starts. It would
    # wrong-case lowercase tool names ("iptables" → "Iptables", "git" → "Git"),
    # distorting technical content for a cosmetic gain. Lowercase sentence
    # starts lose zero information — the model reads them fine.

    text = _restore(text, spans)
    return text.strip()


def compress_chunks(chunks: list[dict], count_tokens, level: str = "safe") -> tuple[list[dict], dict]:
    """Compress every chunk's text (new list), recount tokens with `count_tokens`.

    Returns (new_chunks, stats) with before/after token totals and the level used.
    """
    before = sum(c.get("tokens", 0) for c in chunks)
    out = []
    after = 0
    for c in chunks:
        ctext = compress_text(c["text"], level=level)
        toks = count_tokens(ctext)
        after += toks
        nc = dict(c)
        nc["text"] = ctext
        nc["tokens"] = toks
        nc["compressed"] = level
        out.append(nc)
    saved = before - after
    pct = (saved / before * 100) if before else 0.0
    return out, {
        "level": level,
        "tokens_before": before,
        "tokens_after": after,
        "tokens_saved": saved,
        "percent_saved": round(pct, 1),
    }
