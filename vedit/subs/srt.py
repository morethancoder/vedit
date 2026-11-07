"""SRT text. Arabic lines start with U+200F (RLM) so players lay them out right to left; a token that starts
with a symbol (`.env`, `--flag`, `/start`) gets U+200E (LRM) before it, or the bidi algorithm moves the symbol
to the wrong side of the Latin word."""

from __future__ import annotations

import re

RLM, LRM = "\u200f", "\u200e"
SYMBOLS = ".-_/\\@#~$%&*+=<>|:;!?()[]{}\"'`"
_TOKEN = re.compile(r"\S+")


def stamp(t: float) -> str:
    ms = round(t * 1000)
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def wrap(text: str, width: int = 42) -> str:
    """Two lines of near equal length when the text is longer than `width`."""
    if len(text) <= width:
        return text
    words, best = text.split(), None
    for i in range(1, len(words)):
        a, b = " ".join(words[:i]), " ".join(words[i:])
        score = abs(len(a) - len(b))
        if best is None or score < best[0]:
            best = (score, a + "\n" + b)
    return best[1] if best else text


def mark_symbols(line: str) -> str:
    """LRM before every token that starts with an ASCII symbol and holds Latin letters or digits."""

    def fix(m: re.Match) -> str:
        t = m.group(0)
        if t[0] in SYMBOLS and re.search(r"[A-Za-z0-9]", t):
            return LRM + t
        return t

    return _TOKEN.sub(fix, line)


def rtl_text(text: str) -> str:
    return "\n".join(RLM + mark_symbols(ln) for ln in wrap(text).split("\n"))


def render(cues: list[dict], lines: dict[int, str], rtl: bool) -> str:
    """`cues` have id/t0/t1; `lines` maps id -> text. Numbered 1.. in time order."""
    body = []
    for n, c in enumerate(sorted(cues, key=lambda c: c["id"]), 1):
        text = rtl_text(lines[c["id"]]) if rtl else wrap(lines[c["id"]])
        body.append(f"{n}\n{stamp(c['t0'])} --> {stamp(c['t1'])}\n{text}\n")
    return "\n".join(body)
