"""Reframe: a crop path that keeps the speaker's face in frame when a 16:9 program becomes 9:16, 4:5, 1:1, ...

The crop is full height and as wide as the target aspect allows (9:16 keeps 608 of 1920 px). Its centre
follows the face track like a camera operator would:

- holds still while the face stays inside a dead zone around the crop centre (no jitter on small moves);
- when the face leaves the zone, eases towards it (a smoothed follow, about 1 s to settle);
- on a join (a jump cut) it cuts with the picture: the new piece starts centred on its own face;
- never cuts the face: the face box is pulled fully inside the crop when it fits;
- a piece that moves less than STILL px in total is held at one position.

Times are program seconds; x is the crop's left edge in 1920-wide source pixels. The path is keyed by the face
track, the edl, the aspect and PARAMS, and cached in `.vedit/reframe/<output>.json`.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np

from vedit import formats as fm
from vedit.run import hash_of

SRC_W, SRC_H = 1920, 1080  # face boxes and the crop live in the 1080p proxy's pixels
STEP = 0.25  # seconds between path points (the face track's rate)
DEAD = 0.18  # dead zone: face centre may drift this share of the crop width from its centre before it moves
EASE = 0.22  # per step, the share of the remaining distance covered while following (~1 s to settle)
STILL = 24.0  # px: a piece whose path moves less than this in total is held still
PARAMS = {"step": STEP, "dead": DEAD, "ease": EASE, "still": STILL, "v": 1}


def crop_width(aspect: str, src=(SRC_W, SRC_H)) -> float:
    """Width of a full-height crop of `src` with the target aspect (the whole width when the target is wider)."""
    r = float(fm.ratio(aspect))
    return min(src[0], src[1] * r)


def _face_cx(track, t: float) -> tuple[float | None, list | None]:
    row = track.at(t)
    box = row.get("box")
    if box and row.get("cam"):
        return box[0] + box[2] / 2, box
    return None, None


def path(track, edl, t0: float, t1: float, aspect: str) -> list[dict]:
    """[{t, x}] every STEP over [t0, t1] (program time); x = crop left edge in source px."""
    cw = crop_width(aspect)
    if cw >= SRC_W - 0.5:
        return [{"t": round(t0, 3), "x": 0.0}, {"t": round(t1, 3), "x": 0.0}]
    lo, hi = 0.0, SRC_W - cw
    joins = sorted(j for j in edl.joins() if t0 < j < t1)
    bounds = [t0, *joins, t1]
    out: list[dict] = []
    for a, b in itertools.pairwise(bounds):
        n = max(1, int(np.ceil((b - a) / STEP)))
        ts = [a + k * (b - a) / n for k in range(n + 1)]
        faces = [_face_cx(track, t) for t in ts]
        first = next((c for c, _ in faces if c is not None), SRC_W / 2)
        centre = first
        xs = []
        for cx, box in faces:
            if cx is not None:
                off = cx - centre
                if abs(off) > DEAD * cw:  # outside the dead zone: ease toward the face
                    centre += EASE * (off - np.sign(off) * DEAD * cw)
            x = min(hi, max(lo, centre - cw / 2))
            if box and box[2] <= cw:  # keep the whole face inside the crop
                x = min(max(x, box[0] + box[2] - cw), box[0])
                x = min(hi, max(lo, x))
            xs.append(x)
        if max(xs) - min(xs) < STILL:
            hold = float(np.median(xs))
            if all(
                not b or b[2] > cw or (b[0] >= hold - 0.5 and b[0] + b[2] <= hold + cw + 0.5)
                for _, b in faces
            ):
                xs = [hold] * len(xs)
        seg = [{"t": round(t, 3), "x": round(float(x), 1)} for t, x in zip(ts, xs, strict=True)]
        if out and out[-1]["t"] == seg[0]["t"]:
            out[-1] = {**seg[0], "cut": True}  # the join: the new piece's position wins, as a hard cut
            seg = seg[1:]
        out.extend(seg)
    return out


def x_at(points: list[dict], t: float) -> float:
    """Crop left edge at program time t (linear between points; a `cut` point jumps)."""
    if t <= points[0]["t"]:
        return points[0]["x"]
    for p, q in itertools.pairwise(points):
        if p["t"] <= t <= q["t"]:
            if q.get("cut") and t < q["t"]:
                return p["x"]
            f = (t - p["t"]) / (q["t"] - p["t"]) if q["t"] > p["t"] else 1.0
            return p["x"] + f * (q["x"] - p["x"])
    return points[-1]["x"]


def key(face_key: str, edl_data: dict, t0: float, t1: float, aspect: str) -> str:
    return hash_of(face_key, edl_data, round(t0, 3), round(t1, 3), aspect, PARAMS)


def cached(cache: Path, k: str) -> list[dict] | None:
    try:
        d = json.loads(cache.read_text())
    except (OSError, ValueError):
        return None
    return d["points"] if d.get("key") == k else None


def save(cache: Path, k: str, points: list[dict], aspect: str) -> None:
    cache.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache.with_suffix(".tmp")
    tmp.write_text(json.dumps({"key": k, "aspect": aspect, "crop_w": crop_width(aspect), "points": points}))
    tmp.replace(cache)
