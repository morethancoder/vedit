"""Where graphics go in an output that is not the 16:9 film (9:16, 4:5, 1:1, ...).

The program fills the canvas height and pans along the reframe path (source px x scale `s`). Graphics:

- on-camera text (label, chip, kinetic) keeps its real type size and goes into the *band*: below the face and
  above the burned-in captions, inside the output's safe box. When the band is too short, the captions pause
  while the graphic shows and the band reaches down to the bottom of the safe box.
- a big word behind the head spans the crop, centred on the head, its lower quarter tucked behind the head top
  (the person cut-out stays in front); it lives inside the camera, in source px.
- full-frame scenes (chapter, doodle, screen, plug, custom) stay 1920x1080 compositions shown as a full-width
  card, centred in the safe box, over the blurred camera.

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
        """(x0, x1) free of every platform's UI over the rows [y0, y1]."""
        return fm.clear_span(self.platforms, self.canvas, y0, y1)

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
            f"justify-content: center !important; }}")  # fmt: skip


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
