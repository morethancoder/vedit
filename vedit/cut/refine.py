"""Refine every phrase/filler cut by listening (ported from T tools/refine.py, on splice.py).

ASR word times drift up to ~0.5 s. For each cut the quiet points near its two ends are candidate boundaries;
every candidate splice (1.6 s before + 1.6 s after) goes into ONE WAV, Studio transcribes it in one pass, and the
splice that reads as "words before" + "words after" without the removed words wins. Ties go to the quietest join.
Results are cached per cut in `.vedit/edl/refined.json`, so only new or edited cuts are listened to.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Callable

import numpy as np

from vedit.cut import signal, splice
from vedit.cut.cutsfile import WordCut
from vedit.project import Project
from vedit.words import norm

CTX = 1.6  # seconds of audio kept each side of a candidate splice
K = 3  # quiet-point candidates per side (K*K splices per cut)
NEAR = 4  # words of context each side
LO, HI = 0.6, 0.3  # candidate window around a boundary: [t - LO, t + HI]
REMOVED_PENALTY = 1.5
DIST_PENALTY = 0.15
PARAMS = "v1"  # bump when the numbers above or the scoring change: invalidates the cache


class Refined(dict):
    """{WordCut.key: {"in", "out", "heard", "score", "ctx"}} plus what this run did."""

    listened: int = 0
    cached: int = 0
    splices: int = 0
    minutes: float = 0.0


def lcs(a: list[str], b: list[str]) -> int:
    m = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            m[i + 1][j + 1] = m[i][j] + 1 if x == y else max(m[i][j + 1], m[i + 1][j])
    return m[-1][-1]


def score(before: list[str], after: list[str], gone: list[str], got: list[str], s, e, w0, w1) -> float:
    """Reads as before+after (good), still holds the removed words (bad), far from the word times (bad)."""
    return (
        lcs(before + after, got)
        - REMOVED_PENALTY * lcs(gone, got)
        - DIST_PENALTY * (abs(s - w0) + abs(e - w1))
    )


def candidates(db: np.ndarray, w0: float, w1: float) -> list[tuple[float, float]]:
    starts = signal.minima(db, w0 - LO, w0 + HI, K)
    ends = signal.minima(db, w1 - LO, w1 + HI, K)
    return [(s, e) for s in starts for e in ends if e > s + 0.05]


def context(cut: WordCut, words: list[dict]) -> tuple[list[str], list[str], list[str]]:
    """Normalised tokens: NEAR words before the cut, NEAR after it, and the removed words."""
    before = [norm(w["w"]) for w in words[max(0, cut.i0 - NEAR) : cut.i0]]
    after = [norm(w["w"]) for w in words[cut.i1 + 1 : cut.i1 + 1 + NEAR]]
    gone = [norm(w["w"]) for w in words[cut.i0 : cut.i1 + 1]]
    return [t for t in before if t], [t for t in after if t], [t for t in gone if t]


def ctx_hash(before: list[str], after: list[str], gone: list[str]) -> str:
    blob = json.dumps([PARAMS, before, after, gone], ensure_ascii=False)
    return hashlib.sha1(blob.encode()).hexdigest()[:16]


def pick(scored: list[tuple[float, float, float, float, str]]) -> tuple[float, float, float, str]:
    """Best of (score, join_db, s, e, heard): highest score (to 0.01), ties to the quietest join."""
    best = max(scored, key=lambda r: (round(r[0], 2), -r[1]))
    return best[0], best[2], best[3], best[4]


def _load(path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def _save(path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    os.replace(tmp, path)


def _db(db: np.ndarray, t: float) -> float:
    return float(db[min(len(db) - 1, max(0, round(t * signal.HOP)))])


def cached(paths, cuts: list[WordCut], words_by_clip: dict[str, list[dict]]) -> dict:
    """Cached boundaries still valid for these cuts (same key and context), without listening."""
    cache = _load(paths.edl / "refined.json")
    out = {}
    for c in cuts:
        if c.kind in ("phrase", "filler") and c.pin is None:
            hit = cache.get(c.key)
            if hit and hit.get("ctx") == ctx_hash(*context(c, words_by_clip[c.clip])):
                out[c.key] = hit
    return out


def run(
    project: Project,
    paths,
    cuts: list[WordCut],
    words_by_clip: dict[str, list[dict]],
    log=None,
    progress: Callable[[int, int], None] | None = None,
) -> Refined:
    """Refined boundaries for every unpinned phrase/filler cut (cached ones are not listened to again)."""
    cache_file = paths.edl / "refined.json"
    cache = _load(cache_file)
    out = Refined()
    todo = []  # (cut, before, after, gone, ctx)
    for c in cuts:
        if c.kind not in ("phrase", "filler") or c.pin is not None:
            continue
        before, after, gone = context(c, words_by_clip[c.clip])
        ctx = ctx_hash(before, after, gone)
        hit = cache.get(c.key)
        if hit and hit.get("ctx") == ctx:
            out[c.key] = hit
            out.cached += 1
        else:
            todo.append((c, before, after, gone, ctx))
    if not todo:
        return out

    audio: dict[str, tuple[np.ndarray, int]] = {}
    dbs: dict[str, np.ndarray] = {}
    pieces, index = [], []  # index[i] = (todo n, s, e, join dB)
    sr = 0
    for n, (c, *_rest) in enumerate(todo):
        if c.clip not in audio:
            audio[c.clip] = splice.read_wav(paths.media / f"{c.clip}-48k.wav")
            dbs[c.clip] = signal.envelope_of(*audio[c.clip])
        a, sr = audio[c.clip]
        db = dbs[c.clip]
        for s, e in candidates(db, c.w0, c.w1):
            pieces.append(splice.splice_piece(a, sr, s, e, CTX))
            index.append((n, s, e, _db(db, s) + _db(db, e)))
    out.listened, out.splices = len(todo), len(pieces)
    out.minutes = (sum(len(p) for p in pieces) / sr + splice.GAP * len(pieces)) / 60 if pieces else 0.0
    if log:
        log(f"listening to {len(pieces)} splices for {len(todo)} cuts ({out.minutes:.1f} min of audio)")
    if progress:
        progress(0, len(todo))
    heard = splice.listen(project, pieces, sr, name="refine")
    if progress:
        progress(len(todo), len(todo))

    per: dict[int, list] = {}
    for (n, s, e, jdb), words in zip(index, heard, strict=True):
        c, before, after, gone, _ = todo[n]
        got = [k for k in (norm(w.text) for w in words) if k]
        sc = score(before, after, gone, got, s, e, c.w0, c.w1)
        per.setdefault(n, []).append((sc, jdb, s, e, " ".join(got)))
    for n, (c, _b, _a, _g, ctx) in enumerate(todo):
        if n not in per:  # no quiet candidates: nothing to listen to; the edl snaps the word times
            continue
        sc, s, e, text = pick(per[n])
        entry = {"in": float(s), "out": float(e), "heard": text, "score": round(sc, 2), "ctx": ctx}
        out[c.key] = cache[c.key] = entry
    _save(cache_file, cache)
    return out
