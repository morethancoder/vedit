"""Placement: every layout decision the model used to make by hand (ported from T tools/build.py).

- zooms: the edl's 1.07 punch-ins, kept only where the piece is a camera shot (T `zoom_plan` face test)
- fit-in-shot: an A-roll graphic stays inside one continuous shot (no cut, layout switch or full-frame scene)
- side: away from the face over the whole window (punch-in applied, 40 px margin), checked against the face
- theme: light or dark text from the measured brightness behind the graphic (cached)
- blur: busy backgrounds (screen layouts) get the feathered backdrop blur

All of it is plain arithmetic over a face track (vedit.graphics.faces.FaceTrack: at, over, samples, cam_share)
and a brightness probe, so it is unit-tested on synthetic rows.
"""

from __future__ import annotations

import itertools
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from vedit.run import _timeout_bin, sample_hash

W, H = 1920, 1080
MARGIN = 40  # px around the face that no text may enter
FALLBACK_FACE = [860, 300, 200, 200]  # T: where his face is when none is found
LEFT_ROOM_X = 800  # T: face centre left of this -> text on the right (the wall left of him is empty)

# full-frame kinds: the A-roll blurs and dims behind them; they are breaks for A-roll graphics
FULL_FRAME = {"doodle", "screen", "chapter"}
# A-roll graphics that must sit inside one shot
IN_SHOT = {"label", "chip", "kinetic", "big-number"}
SIDED = {"label", "chip", "kinetic"}

CROSSFADE_GAP = 1.5  # full-frame scenes closer than this hand over directly (T)
CROSSFADE = 0.55
MIN_SHOT = 3.0  # fit-in-shot keeps the first stretch if at least this long, else the longest


# ---- punch-in zooms ----


def zoom_plan(edl, track) -> list[tuple[float, float, float, float]]:
    """(program t, scale, origin x, origin y) at every piece start. A piece keeps the edl's `zoom` only if it is
    a camera shot from start to end (cam share > 0.97, longer than 1.5 s); screen layouts and holds stay 1.0."""
    out = []
    for p in edl.pieces:
        s = p["start"]
        e = s + edl.length(p)
        z = float(p.get("zoom", 1.0))
        if z != 1.0 and ("hold" in p or e - s <= 1.5 or track.cam_share(s, e) <= 0.97):
            z = 1.0
        box = track.at(min(s + 0.3, e)).get("box") or FALLBACK_FACE
        out.append((round(s, 4), z, box[0] + box[2] / 2, box[1] + box[3] / 2))
    return out


def zoomed(box, t: float, zooms) -> list[float]:
    """A face box as it appears on screen at t, after the punch-in (if any)."""
    z, ox, oy = 1.0, 0.0, 0.0
    for jt, zz, x, y in zooms:
        if jt > t + 1e-6:
            break
        z, ox, oy = zz, x, y
    x, y, w, h = box
    return [ox + (x - ox) * z, oy + (y - oy) * z, w * z, h * z]


def face_zone(box, margin: float = MARGIN) -> tuple[float, float, float, float]:
    """The no-text zone around a face box: head and hair above, chin below (T `hits_face`)."""
    x, y, w, h = box
    return (x - 0.15 * w - margin, y - 0.35 * h - margin, x + 1.15 * w + margin, y + 1.1 * h + margin)


def overlaps(a, b) -> bool:
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def hits_face(rect, s: float, e: float, track, zooms, margin: float = MARGIN) -> float:
    """Share of the window's camera-face samples whose zone the rect (x0, y0, x1, y1) touches."""
    rows = [(t, b) for t, b in track.samples(s, e) if list(b) != FALLBACK_FACE]
    if not rows:
        return 0.0
    hit = sum(overlaps(rect, face_zone(zoomed(b, t, zooms), margin)) for t, b in rows)
    return hit / len(rows)


# ---- shots ----


def layout_switches(track, total: float, step: float = 0.25) -> list[float]:
    """Program times where the picture switches between the camera shot and a screen layout (smoothed over 7)."""
    ts = [k * step for k in range(int(total / step))]
    raw = [bool(track.at(t).get("cam")) for t in ts]
    sm = []
    for i in range(len(raw)):
        win = raw[max(0, i - 3) : i + 4]
        sm.append(sum(win) * 2 > len(win))
    return [ts[i] for i in range(1, len(sm)) if sm[i] != sm[i - 1]]


def fit_in_shot(start: float, dur: float, breaks, min_len: float = MIN_SHOT) -> tuple[float, float]:
    """Keep a window inside one continuous shot: the first stretch if long enough, else the longest (T)."""
    end = start + dur
    inside = [b for b in breaks if start + 0.05 < b < end - 0.05]
    if not inside:
        return start, dur
    edges = [start, *inside, end]
    segs = [
        (edges[i] + (0.1 if i else 0), edges[i + 1] - (0.12 if i + 1 < len(edges) - 1 else 0))
        for i in range(len(edges) - 1)
    ]
    pick = segs[0] if segs[0][1] - segs[0][0] >= min_len else max(segs, key=lambda x: x[1] - x[0])
    return round(pick[0], 3), round(pick[1] - pick[0], 3)


def crossfade_scenes(wins: dict[str, list[float]], scene_ids: list[str]) -> list[str]:
    """Full-frame scenes that nearly touch hand over directly: the earlier stays until the next arrives plus a
    crossfade, so the blurred A-roll is never on screen empty. Mutates `wins`; returns notes."""
    notes = []
    order = sorted(scene_ids, key=lambda c: wins[c][0])
    for a, b in itertools.pairwise(order):
        gap = wins[b][0] - (wins[a][0] + wins[a][1])
        if gap < CROSSFADE_GAP:
            wins[a][1] = round(wins[b][0] - wins[a][0] + CROSSFADE, 3)
            notes.append(f"{a} crossfades into {b}")
    return notes


# ---- side, boxes, theme ----


def side_for(s: float, e: float, track) -> tuple[str, bool]:
    """Left or right: away from the face (big camera face or a screen layout's bubble); and whether it's a cam shot."""
    boxes, cam = track.over(s, e)
    if not boxes:
        return "left", cam
    cx = sum(b[0] + b[2] / 2 for b in boxes) / len(boxes)
    return ("right" if cx < LEFT_ROOM_X else "left"), cam


LABEL_BOX = (820, 220)  # fallback size when no measured width is given
EDGE_X = 150  # outer edge of every sided graphic (T)
LABEL_BOTTOM, CHIP_BOTTOM = 110, 118  # T's bottom offsets of the label and chip wraps


def box_for(
    kind: str, side: str, center: bool = False, width: float | None = None, height: float | None = None
) -> tuple[int, int, int, int]:
    """Rough on-screen rect (x, y, w, h) of a sided graphic, as the base templates lay it out (T `box_for`).
    The graphic is flush to its outer edge, so its measured `width` is used: a kinetic line (capped at the 720 px
    column), a label or chip (the widest of its lines). Labels sit 110 px and chips 118 px above the bottom."""
    if kind == "kinetic":
        if center:
            return (160, 330, 1600, 420)
        w = round(min(720, width)) if width else 720
        return (150, 380, w, 320) if side == "left" else (1770 - w, 380, w, 320)
    w = round(width) if width else LABEL_BOX[0]
    h = round(height) if height else LABEL_BOX[1]
    y = H - (CHIP_BOTTOM if kind == "chip" else LABEL_BOTTOM) - h
    return (EDGE_X, y, w, h) if side == "left" else (W - EDGE_X - w, y, w, h)


def rect(box) -> tuple[float, float, float, float]:
    x, y, w, h = box
    return (x, y, x + w, y + h)


KINETIC_COL, KINETIC_MIN = 720, 360  # T's kinetic column, and the narrowest it may get before it touches


def column(kind: str, side: str, s: float, e: float, track, zooms) -> int:
    """Width of the kinetic text column on `side` that stays clear of the face zone over the whole window."""
    zones = [face_zone(zoomed(b, t, zooms)) for t, b in track.samples(s, e) if list(b) != FALLBACK_FACE]
    if not zones:
        return KINETIC_COL
    room = min(z[0] for z in zones) - 150 if side == "left" else (W - 150) - max(z[2] for z in zones)
    return int(max(KINETIC_MIN, min(KINETIC_COL, room)))


class Lum:
    """(mean luma, share of bright pixels) of the program frame at t inside a box, cached per program file."""

    def __init__(self, program: Path, cache_file: Path, grab=None):
        self.program, self.cache_file = Path(program), Path(cache_file)
        self.tag = sample_hash(self.program) or "none"
        self.grab = grab or self._grab
        data = json.loads(self.cache_file.read_text()) if self.cache_file.exists() else {}
        self.cache: dict = data.get(self.tag, {}) if isinstance(data, dict) else {}
        self.frames: dict[float, bytes] = {}

    def _grab(self, t: float) -> bytes:
        """One 192x108 gray frame of the program at t (VideoToolbox decode, time-boxed)."""
        tb = _timeout_bin()
        cmd = [tb, "30"] if tb else []
        cmd += ["nice", "-n", "19", "ffmpeg", "-v", "error", "-hwaccel", "videotoolbox", "-ss", f"{t:.3f}"]
        cmd += ["-i", str(self.program), "-frames:v", "1", "-vf", "scale=192:108,format=gray"]
        cmd += ["-f", "rawvideo", "-"]
        out = subprocess.run(cmd, stdin=subprocess.DEVNULL, capture_output=True, check=False).stdout
        return out if len(out) >= 192 * 108 else bytes(192 * 108)

    def __call__(self, t: float, box) -> tuple[float, float]:
        key = f"{t:.2f}|{','.join(str(round(v)) for v in box)}"
        if key not in self.cache:
            t2 = round(t, 2)
            if t2 not in self.frames:
                self.frames[t2] = self.grab(t2)
            raw = self.frames[t2]
            x, y, w, h = [round(v / 10) for v in box]
            vals = [
                raw[r * 192 + c]
                for r in range(max(0, y), min(108, y + h))
                for c in range(max(0, x), min(192, x + w))
            ]
            n = max(1, len(vals))
            self.cache[key] = [round(sum(vals) / n / 255, 3), round(sum(v > 150 for v in vals) / n, 3)]
        return tuple(self.cache[key])

    def save(self) -> None:
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache_file.write_text(json.dumps({self.tag: self.cache}))


def brightness(s: float, e: float, box, lum) -> tuple[float, float]:
    """Worst case over the window: (max mean, max bright share) at 20/50/80 %."""
    samples = [lum(s + (e - s) * f, box) for f in (0.2, 0.5, 0.8)]
    return max(m for m, _ in samples), max(b for _, b in samples)


def theme_for(s: float, e: float, box, lum) -> str:
    mean, bright = brightness(s, e, box, lum)
    return "light" if mean > 0.58 or bright > 0.6 else "dark"


# ---- one decision per sided cue ----


@dataclass
class Placed:
    side: str = "left"
    theme: str = "dark"
    blur: bool = False  # busy background: feathered backdrop blur + denser shadow
    cam: bool = True
    box: tuple = ()
    face_hit: float = 0.0  # share of face samples the box touches (0 = never)
    width: int = 0  # kinetic: the text column, narrowed to the room beside the face
    notes: list[str] = field(default_factory=list)


def bubble_hit(rect_, boxes, margin: float = MARGIN) -> float:
    """Share of the webcam-bubble boxes (plain, no zoom) the rect touches, with a margin around each."""
    if not boxes:
        return 0.0
    n = sum(overlaps(rect_, (x - margin, y - margin, x + w + margin, y + h + margin)) for x, y, w, h in boxes)
    return n / len(boxes)


def place_sided(
    kind: str,
    s: float,
    e: float,
    track,
    zooms,
    lum,
    center: bool = False,
    width: float | None = None,
    height: float | None = None,
) -> Placed:
    """Side, theme and blur for a label/chip/kinetic over [s, e]; `width` = measured text width, `height` = box
    height (label/chip)."""
    side, cam = side_for(s, e, track)
    p = Placed(cam=cam, blur=not cam)
    bubbles = [] if cam else track.over(s, e)[0]

    def box(sd, cw):
        return box_for(kind, sd, center, cw, height)

    if not cam and not center:  # screen layout: the calmer, darker side (T)
        lb = brightness(s, e, box("left", width), lum)
        rb = brightness(s, e, box("right", width), lum)
        side = "left" if lb[0] + lb[1] <= rb[0] + rb[1] else "right"

    def measure(sd):
        col = column(kind, sd, s, e, track, zooms) if kind == "kinetic" and not center else 0
        cw = min(width, col) if width and col else (col or width)
        r = rect(box(sd, cw))
        return max(hits_face(r, s, e, track, zooms), bubble_hit(r, bubbles)), col, cw

    hit, col, cw = measure(side)
    if hit > 0 and not center:
        other = "left" if side == "right" else "right"
        hit2, col2, cw2 = measure(other)
        if hit2 < hit:
            what = "the webcam bubble" if bubbles else "the face"
            p.notes.append(f"moved {side}->{other}: {what} reaches the {side} side")
            side, hit, col, cw = other, hit2, col2, cw2
    p.side, p.face_hit, p.width = side, round(hit, 3), col
    if col and col < KINETIC_COL:
        p.notes.append(f"column {col}px beside the face")
    p.box = box(side, cw)
    p.theme = theme_for(s, e, p.box, lum)
    if hit > 0:
        p.notes.append(f"touches the {'webcam bubble' if bubbles else 'face zone'} in {hit:.0%} of samples")
    return p
