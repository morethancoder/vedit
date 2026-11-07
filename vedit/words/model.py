"""Word lists per clip and phrase search near an approximate time (ported from T cuts.py `find`)."""

from __future__ import annotations

import difflib
import itertools
import json
import re
from dataclasses import dataclass

from vedit.report import VeditError
from vedit.words.norm import norm, tokens

WINDOW = 6.0  # seconds either side of `near` a match may start (T cuts.py: d < 6)
AMBIGUOUS_GAP = 1.0  # two in-window matches whose distances differ by less than this cannot be told apart
CANDIDATES = 5


STUTTER_GAP = 1.0  # seconds between back-to-back identical copies that count as one stutter


def _stutter(words: list[dict], starts: list[int], n: int) -> bool:
    """Copies at `starts` (sorted) follow each other with no word between and < STUTTER_GAP of silence."""
    return all(
        b == a + n and words[b]["t0"] - words[a + n - 1]["t1"] < STUTTER_GAP
        for a, b in itertools.pairwise(starts)
    )


def _pick(starts: list[int], pick: str | int, phrase: str, near: str) -> int:
    if pick == "first":
        return starts[0]
    if pick == "last":
        return starts[-1]
    if isinstance(pick, int) and not isinstance(pick, bool) and 1 <= pick <= len(starts):
        return starts[pick - 1]
    raise VeditError(
        f"pick {pick!r} for {phrase!r} near {near}: use first, last or 1..{len(starts)} "
        f"({len(starts)} match{'es' if len(starts) != 1 else ''} in the window)"
    )


class NoMatch(VeditError):
    candidates: tuple | list = ()


class AmbiguousMatch(VeditError):
    candidates: tuple | list = ()


@dataclass
class Span:
    clip: str
    i0: int  # first word index
    i1: int  # last word index (inclusive)
    t0: float
    t1: float
    text: str


def load(paths, clip: str) -> list[dict]:
    """Words of a clip from .vedit/words/<clip>.json: [{t0, t1, w}]."""
    f = paths.words / f"{clip}.json"
    if not f.exists():
        raise VeditError(f"no words for clip {clip} ({f})", next="vedit ingest")
    return json.loads(f.read_text())


def parse_near(near: str) -> tuple[str, float]:
    """'A 245.0' -> ('A', 245.0)."""
    m = re.fullmatch(r"\s*(\S+)\s+(\d+(?:\.\d+)?)\s*", str(near))
    if not m:
        raise VeditError(f"bad near {near!r}: expected '<clip> <seconds>', e.g. 'A 245.0'")
    return m.group(1), float(m.group(2))


def _candidates(words: list[dict], want: list[str], clip: str, t: float) -> list[dict]:
    keys = [norm(w["w"]) for w in words]
    target = " ".join(want)
    out = []
    n = len(want)
    for size in {max(1, n - 1), n, n + 1}:
        for i in range(len(words) - size + 1):
            sim = difflib.SequenceMatcher(None, target, " ".join(keys[i : i + size])).ratio()
            out.append(
                {
                    "clip": clip,
                    "time": words[i]["t0"],
                    "text": " ".join(w["w"] for w in words[i : i + size]),
                    "similarity": round(sim, 2),
                    "_d": abs(words[i]["t0"] - t),
                }
            )
    # best similarity first; of equals the nearest in time; one row per start time
    out.sort(key=lambda c: (-c["similarity"], c["_d"]))
    seen, top = set(), []
    for c in out:
        if c["time"] not in seen:
            seen.add(c["time"])
            top.append(c)
        if len(top) == CANDIDATES:
            break
    for c in top:
        del c["_d"]
    return top


def _listing(cands: list[dict]) -> str:
    return "\n".join(
        f"  {c['clip']} {c['time']:.2f}  {c['text']}  (similarity {c['similarity']:.2f})" for c in cands
    )


def find(
    words_by_clip: dict[str, list[dict]],
    phrase: str,
    near: str = "A 245.0",
    window: float = WINDOW,
    pick: str | int | None = None,
) -> Span:
    """Span of the exact normalised token sequence whose start is closest to `near`.

    Raises NoMatch if none starts within `window` seconds, AmbiguousMatch if the two nearest are within
    AMBIGUOUS_GAP seconds of the same distance from `near`, unless they are a stutter: identical copies
    back to back (no word between, gap < STUTTER_GAP), where the FIRST copy wins (a restart keeps the last
    take). `pick` ("first", "last" or a 1-based n) chooses among all in-window matches in time order.
    """
    clip, t = parse_near(near)
    if clip not in words_by_clip:
        raise VeditError(
            f"near {near!r}: no words loaded for clip {clip} (have: {', '.join(words_by_clip) or 'none'})"
        )
    words = words_by_clip[clip]
    want = tokens(phrase)
    if not want:
        raise VeditError(f"phrase {phrase!r} has no words to match")
    keys = [norm(w["w"]) for w in words]
    hits = []
    for i in range(len(words) - len(want) + 1):
        if keys[i : i + len(want)] == want:
            d = abs(words[i]["t0"] - t)
            if d < window:
                hits.append((d, i))
    hits.sort()
    if not hits:
        cands = _candidates(words, want, clip, t)
        err = NoMatch(
            f"no match for {phrase!r} within {window:g}s of {near}. Closest:\n" + _listing(cands),
            next="move `near` to the right time or fix the words (check .vedit/words)",
        )
        err.candidates = cands
        raise err
    if pick is not None:
        i0 = _pick(sorted(i for _, i in hits), pick, phrase, near)
        hits = [(0.0, i0)]
    close = sorted(i for d, i in hits if d - hits[0][0] < AMBIGUOUS_GAP)
    if len(close) > 1 and _stutter(words, close, len(want)):
        hits = [(0.0, close[0])]
    if len(hits) > 1 and hits[1][0] - hits[0][0] < AMBIGUOUS_GAP:
        cands = [
            {
                "clip": clip,
                "time": words[i]["t0"],
                "text": " ".join(w["w"] for w in words[i : i + len(want)]),
                "similarity": 1.0,
            }
            for _, i in hits[:CANDIDATES]
        ]
        err = AmbiguousMatch(
            f"{phrase!r} matches {len(hits)} places near {near}:\n" + _listing(cands),
            next="move `near` closer to the one you mean, quote more words, or add `pick: first|last|<n>`",
        )
        err.candidates = cands
        raise err
    i0 = hits[0][1]
    i1 = i0 + len(want) - 1
    return Span(clip, i0, i1, words[i0]["t0"], words[i1]["t1"], " ".join(w["w"] for w in words[i0 : i1 + 1]))
