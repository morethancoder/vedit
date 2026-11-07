"""Edit decision list: resolved cuts -> program pieces (ported from T tools/cuts.py `main()` and build.py `zoom_plan`)."""

from __future__ import annotations

import numpy as np

from vedit.cut.cutsfile import WordCut
from vedit.cut.signal import SIL_DB, quietest, silences
from vedit.words import parse_near

SNAP = 0.12  # how far a boundary may move to find quiet
GRID = 30  # pieces sit on a 1/30 s grid
TAIL = 1.6  # footage kept running after the last word, under the fade to black
MIN_PIECE = 0.2
MERGE_GAP = 0.07
OPENING = 0.4  # the first clip opens on the first kept piece that ends after this
HOLD = 1.8
HOLD_REACH = 0.2
ZOOM = 1.07
ZOOM_MIN = 1.5  # a piece must run longer than this to punch in
PAUSES = {"max": 0.5, "keep": 0.3}


def subtract(keep: list[tuple[float, float]], cut: tuple[float, float]) -> list[tuple[float, float]]:
    out = []
    for a, b in keep:
        if cut[1] <= a or cut[0] >= b:
            out.append((a, b))
            continue
        if cut[0] > a:
            out.append((a, cut[0]))
        if cut[1] < b:
            out.append((cut[1], b))
    return out


def boundaries(c: WordCut, refined: dict, db: np.ndarray, words: list[dict]) -> tuple[float, float]:
    """pin > refined > quietest within SNAP of the word times."""
    if c.pin:
        return c.pin
    r = refined.get(c.key)
    if r:
        return r["in"], r["out"]
    if c.kind == "pin":
        return c.w0, c.w1
    w1 = c.w1
    if c.kind == "filler" and c.i1 + 1 >= len(words):
        w1 = words[c.i1]["t1"]  # T: the last word has no next word, its own end
    return quietest(db, c.w0, SNAP), quietest(db, w1, SNAP)


def zoom_pieces(pieces: list[dict], zoom_clips: set[str]) -> int:
    """Punch in on every other jump cut between camera shots; writes `zoom` only when it is ZOOM."""
    state, n = 1.0, 0
    for k, p in enumerate(pieces):
        if k == 0 or "hold" in p or p["clip"] not in zoom_clips:
            state = 1.0
            continue
        whole = p["out"] - p["in"] > ZOOM_MIN and "hold" not in pieces[k - 1]
        state = (ZOOM if state == 1.0 else 1.0) if whole else 1.0
        if state == ZOOM:
            p["zoom"] = ZOOM
            n += 1
    return n


def build(
    cuts: list[WordCut],
    refined: dict,
    envelopes: dict[str, np.ndarray],
    words_by_clip: dict[str, list[dict]],
    durations: dict[str, float],
    pauses: dict | None = None,
    chapters: list[tuple[str, float, float]] | None = None,
    end: str | None = None,
    zoom_clips: set[str] | None = None,
) -> tuple[dict, dict]:
    """Returns (edl `{total, fade_start, pieces}`, info for the report).

    chapters: (clip, source time, hold seconds). end "last-word": keep TAIL of picture after the last word
    of the last clip and fade_start = the end of that word. Clips run in the order of `durations`.
    """
    pz = {**PAUSES, **(pauses or {})}
    clips = list(durations)
    hold_list = chapters or []
    edl: list[dict] = []
    info = {"cuts": {}, "pins": 0, "pauses": 0, "holds": 0, "clips": {}, "notes": []}
    fade_src = None
    for ci, clip in enumerate(clips):
        words, db, dur = words_by_clip.get(clip, []), envelopes[clip], durations[clip]
        spans: list[tuple[float, float, str | None]] = []
        for c in (c for c in cuts if c.clip == clip):
            a, b = boundaries(c, refined, db, words)
            spans.append((a, b, c.label))
            info["cuts"][c.kind] = info["cuts"].get(c.kind, 0) + 1
            info["pins"] += c.pin is not None
        for a, b in silences(db, SIL_DB):
            if b - a > pz["max"]:
                spans.append((a + pz["keep"] / 2, b - pz["keep"] / 2, None))
                info["pauses"] += 1
        keep = [(0.0, dur)]
        for a, b, _ in sorted(spans, key=lambda s: (s[0], s[1])):
            keep = subtract(keep, (a, b))
        if ci == 0:  # the video opens on the first kept piece, not on the breath before it
            keep = [(a, b) for a, b in keep if b > OPENING]
        if ci == len(clips) - 1 and end == "last-word" and words:
            last_word = words[-1]["t1"]
            keep = [(a, b) for a, b in keep if a < last_word]
            if keep:
                keep[-1] = (keep[-1][0], min(dur, last_word + TAIL))
            fade_src = last_word
        q = [(round(a * GRID) / GRID, round(b * GRID) / GRID) for a, b in keep]
        q = [(a, b) for a, b in q if b - a >= MIN_PIECE]
        merged: list[tuple[float, float]] = []
        for a, b in q:
            if merged and a - merged[-1][1] < MERGE_GAP:
                merged[-1] = (merged[-1][0], b)
            else:
                merged.append((a, b))
        hold_at: dict[float, float] = {}
        for hc, ht, hd in hold_list:
            if hc != clip or not merged:
                continue
            at = round(quietest(db, min(ht, merged[-1][1] - 0.05), HOLD_REACH) * GRID) / GRID
            out, inside = [], False
            for a, b in merged:
                if a < at < b:
                    out += [(a, at), (at, b)]
                    inside = True
                else:
                    out.append((a, b))
            if not inside:  # the hold point fell in a removed pause: hold after the previous kept piece
                before = [b for a, b in merged if b <= at]
                if not before:
                    info["notes"].append(
                        f"chapter hold at {clip} {ht:g} falls before the first kept piece: skipped"
                    )
                    continue
                at = max(before)
            merged = out if inside else merged
            hold_at[round(at, 4)] = hd
        for a, b in merged:
            edl.append({"clip": clip, "in": round(a, 4), "out": round(b, 4)})
            if round(b, 4) in hold_at:
                edl.append(
                    {"clip": clip, "in": round(b, 4), "out": round(b, 4), "hold": hold_at[round(b, 4)]}
                )
                info["holds"] += 1
        info["clips"][clip] = {
            "source": round(dur, 2),
            "kept": round(sum(b - a for a, b in merged), 2),
            "pieces": len(merged),
        }
    t, fade_start = 0.0, None
    last = clips[-1] if clips else None
    for p in edl:
        p["start"] = round(t, 4)
        if fade_src is not None and p["clip"] == last and "hold" not in p and p["in"] <= fade_src < p["out"]:
            fade_start = round(t + fade_src - p["in"], 4)
        t += p.get("hold", p["out"] - p["in"])
    info["zoomed"] = zoom_pieces(edl, zoom_clips or set())
    info["pieces"] = len(edl)
    return {"total": round(t, 4), "fade_start": fade_start, "pieces": edl}, info


def chapter_holds(chapters, seconds: float = HOLD) -> list[tuple[str, float, float]]:
    """cuts.yaml chapters -> (clip, source time, hold seconds)."""
    out = []
    for ch in chapters:
        clip, t = parse_near(ch.near)
        out.append((clip, t, seconds))
    return out
