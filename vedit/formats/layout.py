"""Where graphics go in an output that is not the 16:9 film (9:16, 4:5, 1:1, ...).

The program fills the canvas height and pans along the reframe path (source px x scale `s`). Graphics:

- on-camera text (label, chip, kinetic) keeps its real type size and goes into the *band*: below the face and
  above the burned-in captions, inside the output's safe box. When the band is too short, the captions pause
  while the graphic shows and the band reaches down to the bottom of the safe box.
- a big word behind the head spans the crop, centred on the head, its lower quarter tucked behind the head top
  (the person cut-out stays in front); it lives inside the camera, in source px.
- full-frame scenes (chapter, screen, plug, custom) stay 1920x1080 compositions shown as a full-width card,
  centred in the safe box, on a plain background (blur only when the output asks for `fill: blur`).
- a doodle splits the frame: its drawing, in pages of beats whose labels stay readable (vedit.doodles.spec.pages),
  fills a panel in the top half on a plain background; the captions move up to the seam under it; the camera
  zooms out about the face and slides down so the whole head sits below the captions.

Every number here is in output px unless it says source px.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from vedit import formats as fm
from vedit.formats import reframe as rf
from vedit.graphics.big import text_em

TEXT = {"label", "chip", "kinetic"}
CARD = {"chapter", "doodle", "screen", "plug", "custom"}
FACE_GAP = 36  # px between the face and the band
CAPTION_LINES = 2
CAPTION_PX = 64  # caption type size on a 1080-wide canvas
CAPTION_GAP = 24
NEED = {"label": 200, "chip": 150, "kinetic": 150}  # band height each type needs (px)
KINETIC_PX = 92
BIG_MAX, BIG_MIN = 300, 90  # source px
BIG_TUCK = 0.25  # share of the word's height behind the head top


@dataclass
class Geometry:
    """One output's frame: canvas, safe box, the program scale and pan, and the program span it shows."""

    oid: str
    aspect: str
    canvas: tuple[int, int]
    safe: fm.Box
    points: list[dict]  # reframe path (program time)
    t0: float
    t1: float
    captions: bool
    platforms: list[str] = field(default_factory=list)
    crop_w: float = field(init=False)
    s: float = field(init=False)  # output px per source px

    def __post_init__(self):
        self.crop_w = rf.crop_width(self.aspect)
        self.s = self.canvas[1] / rf.SRC_H

    @property
    def caption_h(self) -> float:
        return CAPTION_LINES * CAPTION_PX * 1.25 + 28 if self.captions else 0.0

    @property
    def caption_top(self) -> float:
        return self.safe.y1 - self.caption_h

    def clear(self, y0: float, y1: float) -> tuple[float, float]:
        """(x0, x1) free of every platform's UI over the rows [y0, y1], symmetric about the frame's centre: the
        wider inset (usually the right-hand button rail) is mirrored on the other side, so text centres on the
        frame and not on a box pushed to one side."""
        x0, x1 = fm.clear_span(self.platforms, self.canvas, y0, y1)
        inset = max(x0, self.canvas[0] - x1)
        return inset, self.canvas[0] - inset

    def to_out_x(self, t: float, x_src: float) -> float:
        return (x_src - rf.x_at(self.points, t)) * self.s


def geometry(out, canvas_size=None, points=None, t0=0.0, t1=0.0) -> Geometry:
    size = canvas_size or fm.canvas(out.aspect)
    return Geometry(out.id, out.aspect, size, fm.safe_box(out.platforms, size), points or [], t0, t1,
                    out.captions == "burned", list(out.platforms))  # fmt: skip


def face_bottom(geo: Geometry, track, s: float, e: float) -> float:
    """Lowest the face comes over [s, e], in output px (the camera fills the canvas height)."""
    boxes, _ = track.over(s, e)
    if not boxes:
        return geo.canvas[1] * 0.45
    return max(b[1] + b[3] for b in boxes) * geo.s


@dataclass
class Slot:
    """Where one on-camera text graphic goes, and whether the captions pause for it."""

    top: float
    bottom: float
    pause_captions: bool
    fs: float | None = None  # kinetic: line size that fits the band width
    x0: float | None = None  # band left/right edges (default: the safe box)
    x1: float | None = None


def band(geo: Geometry, track, typ: str, s: float, e: float, em: float = 0.0) -> Slot:
    top = max(geo.safe.y, face_bottom(geo, track, s, e) + FACE_GAP)
    bottom = geo.caption_top - (CAPTION_GAP if geo.captions else 0)
    pause = False
    if bottom - top < NEED[typ]:
        pause, bottom = geo.captions, geo.safe.y1
    if bottom - top < NEED[typ]:  # still no room: sit on the bottom of the safe box over the chest
        top = bottom - NEED[typ]
    x0, x1 = geo.clear(top, bottom)
    fs = None
    if typ == "kinetic" and em > 0:
        fs = max(44.0, min(KINETIC_PX, 0.95 * (x1 - x0) / em))
    return Slot(round(top, 1), round(bottom, 1), pause, None if fs is None else round(fs, 1), x0, x1)


def wrap_css(geo: Geometry, typ: str, slot: Slot) -> str:
    """CSS appended after the type template: moves its `.wrap` into the band (a pack convention, packcheck)."""
    _w, h = geo.canvas
    sx = geo.safe.x if slot.x0 is None else slot.x0
    sw = geo.safe.w if slot.x1 is None else slot.x1 - sx
    if typ == "kinetic":
        css = (f".wrap {{ left: {sx:.0f}px !important; right: auto !important; width: {sw:.0f}px !important; "
               f"top: {slot.top:.0f}px !important; bottom: {h - slot.bottom:.0f}px !important; "
               f"justify-content: center !important; }}\n"
               f".line {{ text-align: center !important; }}")  # fmt: skip
        if slot.fs:
            css += f"\n.line {{ font-size: {slot.fs:.0f}px !important; }}"
        return css
    return (f".wrap {{ left: {sx:.0f}px !important; right: auto !important; width: {sw:.0f}px !important; "
            f"max-width: {sw:.0f}px !important; top: auto !important; bottom: {h - slot.bottom:.0f}px !important; "
            f"justify-content: center !important; }}\n"
            f".txt {{ align-items: center !important; text-align: center !important; }}")  # fmt: skip


def big(geo: Geometry, track, s: float, e: float, word: str, adv: dict, track_em: float = -0.03) -> dict:
    """Big word over the crop, centred on the head (source px, inside the camera)."""
    mid = (s + e) / 2
    x0 = rf.x_at(geo.points, mid)
    boxes = [b for _, b in track.samples(s, e)]
    top = sorted(b[1] for b in boxes)[len(boxes) // 2]
    cx = sorted(b[0] + b[2] / 2 for b in boxes)[len(boxes) // 2]
    total = text_em(word, adv, track_em)
    fs = max(BIG_MIN, min(BIG_MAX, 0.92 * geo.crop_w / total))
    width = total * fs
    left = min(max(cx - width / 2, x0 + 0.04 * geo.crop_w), x0 + 0.96 * geo.crop_w - width)
    return {"side": "center", "fs": round(fs), "left": round(left), "top": round(top - (1 - BIG_TUCK) * fs),
            "width": round(width), "tuck": BIG_TUCK, "drift": 0}  # fmt: skip


def card(geo: Geometry) -> dict:
    """A 1920x1080 full-frame scene as a card centred in the safe box, as wide as the rows it covers allow
    (full width unless a platform's side UI reaches into those rows): {k, x, y, w, h} in output px."""
    w, _ = geo.canvas
    x0, x1 = 0.0, float(w)
    for _ in range(3):  # the rows the card covers depend on its width
        h = 1080 * (x1 - x0) / 1920
        y = geo.safe.y + (geo.safe.h - h) / 2
        c0, c1 = geo.clear(y, y + h)
        x0 = 0.0 if c0 <= geo.safe.x + 0.5 else c0  # only named UI narrows a card, not the side margins
        x1 = float(w) if c1 >= geo.safe.x1 - 0.5 else c1
    k = (x1 - x0) / 1920
    h = 1080 * k
    y = geo.safe.y + (geo.safe.h - h) / 2
    return {"k": round(k, 5), "x": round(x0, 1), "y": round(y, 1), "w": round(x1 - x0, 1), "h": round(h, 1)}


SPLIT = 0.5  # the doodle panel ends at or above this share of the canvas height
PANEL_MARGIN = 24  # px inside the panel area on each side
HEAD = 1.5  # head height (hair to chin) in face-box heights
HEAD_ROOM = 0.7  # face-box centre to the top of the hair, in face-box heights


def split_area(geo: Geometry) -> tuple[float, float, float, float]:
    """(x0, y0, x1, y1) the doodle panel may use in a split: inside the safe box, above the split line, centred,
    with the bottom chosen for the largest area (a side button column that starts lower narrows the rows below)."""
    top = geo.safe.y
    best = None
    for bottom in range(int(top) + 300, round(geo.canvas[1] * SPLIT) + 1, 10):
        x0, x1 = geo.clear(top, bottom)
        w, h = x1 - x0 - 2 * PANEL_MARGIN, bottom - top - 2 * PANEL_MARGIN
        if best is None or w * h > best[0]:
            best = (w * h, (x0 + PANEL_MARGIN, top + PANEL_MARGIN, x1 - PANEL_MARGIN, bottom - PANEL_MARGIN))
    return best[1]


def fit(area: tuple[float, float, float, float], box: tuple[float, float, float, float]) -> dict:
    """`box` (in a 1920x1080 scene) scaled to fit `area`, centred: {k, x, y, w, h, bx, by} in output px."""
    aw, ah = area[2] - area[0], area[3] - area[1]
    bw, bh = box[2] - box[0], box[3] - box[1]
    k = min(aw / bw, ah / bh, 1.25)
    pw, ph = bw * k, bh * k
    return {"k": round(k, 5), "x": round(area[0] + (aw - pw) / 2, 1), "y": round(area[1] + (ah - ph) / 2, 1),
            "w": round(pw, 1), "h": round(ph, 1), "bx": box[0], "by": box[1]}  # fmt: skip


def split_camera(geo: Geometry, track, s: float, e: float, area: tuple[float, float, float, float]) -> dict:
    """The lower half of a split: captions move up to the seam under the panel, and the camera zooms out (about
    the face, which the crop already centres) and slides down so the whole head sits below the captions.
    {cap_dy, z, oy, dy, fill_h}: caption shift, zoom, zoom origin y, slide, height of the plain fill on top."""
    w, h = geo.canvas
    seam = area[3] + PANEL_MARGIN
    cap_dy = round(seam - geo.caption_top, 1) if geo.captions else 0.0
    below = seam + (geo.caption_h + 16 if geo.captions else 16)
    boxes, _ = track.over(s, e)
    if boxes:
        cys = sorted((b[1] + b[3] / 2) * geo.s for b in boxes)
        fhs = sorted(b[3] * geo.s for b in boxes)
        oy, fh = cys[len(cys) // 2], fhs[len(fhs) // 2]
    else:
        oy, fh = h * 0.3, h * 0.3
    room = (h - 120) - below
    z = min(1.0, 0.8 * room / (HEAD * fh))
    target = below + HEAD_ROOM * fh * z
    z = max(z, (h - target) / (h - oy) + 0.01)  # the zoomed frame must still reach the bottom edge
    xs = [p["x"] * geo.s for p in geo.points if s - 1 <= p["t"] <= e + 1] or [geo.points[0]["x"] * geo.s]
    for X in xs:  # and both side edges, wherever the crop pans in this window
        z = max(z, (w / 2) / (w / 2 + X) + 0.01, (w / 2) / (1920 * geo.s - X - w / 2) + 0.01)
    z = min(1.0, z)
    dy = target - oy
    top = target - oy * z
    return {"cap_dy": cap_dy, "z": round(z, 4), "oy": round(oy, 1), "dy": round(dy, 1),
            "fill_h": round(max(seam, top), 1)}  # fmt: skip
