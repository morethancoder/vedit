"""Word anchors for cues: phrase search in source time, forward search, kept-range check, spoken onsets."""

from __future__ import annotations

from vedit.words import Edl, Span, norm, tokens
from vedit.words.model import _candidates, _listing

FORWARD = 90.0  # seconds after the anchor that `until` and beats are searched
MAX_SPOKEN = 400  # words of transcript timed per cue


def spans(words: list[dict], phrase: str, clip: str) -> list[Span]:
    """Every exact normalised match of `phrase` in a clip's words, in order."""
    want = tokens(phrase)
    if not want:
        return []
    keys = [norm(w["w"]) for w in words]
    out = []
    for i in range(len(words) - len(want) + 1):
        if keys[i : i + len(want)] == want:
            j = i + len(want) - 1
            out.append(
                Span(clip, i, j, words[i]["t0"], words[j]["t1"], " ".join(w["w"] for w in words[i : j + 1]))
            )
    return out


def first_after(words: list[dict], phrase: str, clip: str, t_from: float, t_to: float) -> Span | None:
    """The first match whose start lies in [t_from, t_to]."""
    for s in spans(words, phrase, clip):
        if t_from <= s.t0 <= t_to:
            return s
    return None


def closest(words: list[dict], phrase: str, clip: str, t: float) -> str:
    """The nearest transcript candidates for a phrase that did not match, as a listing."""
    want = tokens(phrase)
    return _listing(_candidates(words, want, clip, t)) if want else ""


def kept(edl: Edl, clip: str, t0: float, t1: float, tol: float = 0.02) -> bool:
    """True when source range t0..t1 of the clip lies inside one kept (non-hold) edl piece."""
    return any(
        p["clip"] == clip and "hold" not in p and p["in"] - tol <= t0 and t1 <= p["out"] + tol
        for p in edl.pieces
    )


def words_kept(edl: Edl, clip: str, words: list[dict], i0: int, i1: int) -> bool:
    """True when every word i0..i1 has its middle inside a kept piece (a trimmed pause between words is fine)."""
    return all(kept(edl, clip, (w["t0"] + w["t1"]) / 2, (w["t0"] + w["t1"]) / 2) for w in words[i0 : i1 + 1])


def spoken_onsets(edl: Edl, clip: str, words: list[dict], i0: int, t_max: float) -> list[float]:
    """Program onsets of the kept transcript words from index i0 whose source start is <= t_max."""
    out = []
    for w in words[i0 : i0 + MAX_SPOKEN]:
        if w["t0"] > t_max:
            break
        if kept(edl, clip, w["t0"], w["t0"]):
            out.append(edl.g(clip, w["t0"]))
    return out
