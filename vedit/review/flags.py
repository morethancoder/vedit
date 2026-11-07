"""Pure review logic: each graphic's peak from its GSAP tweens, and the four flags code can measure.

Input is what the in-page probe reports (probe.js): per graphic its tweens `{s, d, keys, opacity, ease}` in
the graphic's local time, and at the peak every visible text element `{text, box: [x0, y0, x1, y1], px,
color}` in 1920x1080 composition pixels. Pixels for the contrast check come from the snapshot PNG.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

# Thresholds (1080p composition pixels).
FACE_MARGIN = 40  # build keeps graphics 40 px off the face box (docs/pipeline.md "never on his face")
MIN_TEXT_PX = (
    22  # smallest secondary text the packs use (violet chip label 22 px); smaller is unreadable on a phone
)
MIN_CONTRAST = 3.0  # WCAG AA ratio for large text; every video graphic is large text
EXIT_SLACK = 0.05  # s: a draw may end this close to the exit start without counting as "still drawing"
PEAK_SETTLE = 0.15  # s after the last element lands, so the snapshot shows it at rest
INK_DIST = 60  # RGB distance under which a pixel counts as the text's own colour (glyph + anti-aliasing core)
MIN_INK = 0.02  # share of glyph pixels below which the text is not really on screen (clipped, mid write-on)

# Tween properties that make something appear or draw; a tween with only motion keys (x, y, rotation) is idle
# movement (float, spin, drift) and may run through the exit by design.
DRAW_KEYS = {
    "opacity", "autoAlpha", "strokeDashoffset", "strokeDasharray", "drawSVG", "clipPath", "scale",
    "scaleX", "scaleY", "width", "height", "text",
}  # fmt: skip


@dataclass
class Flag:
    code: str  # face | small | contrast | drawing
    message: str

    def to_dict(self) -> dict:
        return {"code": self.code, "message": self.message}


# ---- timing ----


def is_exit(tw: dict) -> bool:
    return tw.get("opacity") is not None and float(tw["opacity"]) <= 0.001


def is_draw(tw: dict) -> bool:
    return not is_exit(tw) and bool(DRAW_KEYS & set(tw.get("keys") or []))


def exit_at(tweens: list[dict], dur: float) -> float:
    """Local second the graphic starts to leave: the last fade-to-0 tween, else its window end."""
    outs = [float(t["s"]) for t in tweens if is_exit(t)]
    return min(max(outs), dur) if outs else dur


def late_draws(tweens: list[dict], dur: float) -> list[float]:
    """Seconds each draw tween runs past the exit start (only those that do, beyond EXIT_SLACK)."""
    ex = exit_at(tweens, dur)
    ends = (float(t["s"]) + float(t["d"]) for t in tweens if is_draw(t))
    return sorted(round(e - ex, 2) for e in ends if e > ex + EXIT_SLACK)


def peak_of(tweens: list[dict], dur: float) -> float:
    """Local peak second: everything that draws has landed (+ PEAK_SETTLE), before the exit starts.

    No draw tweens: the middle of the window. A draw still running at the exit: just before the exit.
    """
    ex = exit_at(tweens, dur)
    last = ex - EXIT_SLACK
    ends = [float(t["s"]) + float(t["d"]) for t in tweens if is_draw(t)]
    if not ends:
        return round(max(0.0, min(dur / 2, last)), 3)
    if max(ends) > ex + EXIT_SLACK:
        return round(max(0.0, last), 3)
    return round(max(0.0, min(max(ends) + PEAK_SETTLE, last)), 3)


# ---- geometry ----


def grow(box, m: float) -> list[float]:
    x0, y0, x1, y1 = box
    return [x0 - m, y0 - m, x1 + m, y1 + m]


def overlap(a, b) -> bool:
    """Boxes [x0, y0, x1, y1] share area."""
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def xywh_to_box(b) -> list[float]:
    x, y, w, h = b
    return [x, y, x + w, y + h]


def zoomed(box, zoom: tuple[float, float, float] | None) -> list[float]:
    """A footage box under the punch-in `(scale, ox, oy)` (CSS scale around transform-origin px)."""
    if not zoom or zoom[0] == 1.0:
        return list(box)
    z, ox, oy = zoom
    x0, y0, x1, y1 = box
    return [ox + (x0 - ox) * z, oy + (y0 - oy) * z, ox + (x1 - ox) * z, oy + (y1 - oy) * z]


# ---- colour ----

_RGB = re.compile(r"rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)(?:[,\s/]+([\d.]+%?))?\s*\)")


def parse_color(css: str) -> tuple[tuple[int, int, int], float] | None:
    """`rgb(...)`, `rgba(...)` or `#rrggbb` -> ((r, g, b), alpha)."""
    s = (css or "").strip()
    m = _RGB.match(s)
    if m:
        a = m.group(4)
        alpha = 1.0 if a is None else (float(a[:-1]) / 100 if a.endswith("%") else float(a))
        return (round(float(m.group(1))), round(float(m.group(2))), round(float(m.group(3)))), alpha
    if re.fullmatch(r"#[0-9a-fA-F]{6}", s):
        return (int(s[1:3], 16), int(s[3:5], 16), int(s[5:7], 16)), 1.0
    return None


def luminance(rgb) -> float:
    """WCAG relative luminance of an sRGB colour (0-255 channels)."""

    def ch(v: float) -> float:
        c = v / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)


def contrast_ratio(a, b) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def background_of(crop_rgb: np.ndarray, ink) -> tuple[int, int, int] | None:
    """Median colour of the pixels in a text box that are not the text's own colour (the frame behind it,
    darkened by the text shadow where there is one). None when hardly any glyph pixels are visible."""
    px = crop_rgb.reshape(-1, 3).astype(np.int32)
    if len(px) == 0:
        return None
    dist = np.sqrt(((px - np.array(ink, np.int32)) ** 2).sum(axis=1))
    is_ink = dist < INK_DIST
    if is_ink.mean() < MIN_INK or is_ink.all():
        return None
    med = np.median(px[~is_ink], axis=0)
    return int(med[0]), int(med[1]), int(med[2])


# ---- flags ----


def text_flags(texts: list[dict], face_box, frame_rgb: np.ndarray | None) -> tuple[list[Flag], list[dict]]:
    """Flags for the texts of one graphic at its peak, plus per-text measurements (px, contrast).

    face_box: the face [x0, y0, x1, y1] in composition px (zoom applied), or None to skip the face check.
    frame_rgb: the snapshot as an RGB array (H x W x 3), or None to skip contrast.
    """
    flags: list[Flag] = []
    rows = []
    near = grow(face_box, FACE_MARGIN) if face_box else None
    for t in texts:
        box = [float(v) for v in t["box"]]
        label = _short(t.get("text", ""))
        row = {"text": t.get("text", ""), "box": [round(v) for v in box], "px": t.get("px")}
        if near and overlap(box, near):
            flags.append(Flag("face", f"text {label} is within {FACE_MARGIN} px of the face"))
        px = t.get("px")
        if px is not None and float(px) < MIN_TEXT_PX:
            flags.append(Flag("small", f"text {label} is {float(px):.0f} px (< {MIN_TEXT_PX})"))
        col = parse_color(t.get("color", ""))
        if frame_rgb is not None and col is not None:
            h, w = frame_rgb.shape[:2]
            x0, y0 = max(0, int(box[0])), max(0, int(box[1]))
            x1, y1 = min(w, int(box[2] + 0.999)), min(h, int(box[3] + 0.999))
            bg = background_of(frame_rgb[y0:y1, x0:x1], col[0]) if x1 > x0 and y1 > y0 else None
            if bg is not None:
                ratio = round(contrast_ratio(col[0], bg), 2)
                row["contrast"] = ratio
                if ratio < MIN_CONTRAST:
                    flags.append(Flag("contrast", f"text {label} contrast {ratio}:1 (< {MIN_CONTRAST:g})"))
        rows.append(row)
    return _merge(flags), rows


def drawing_flag(tweens: list[dict], dur: float) -> Flag | None:
    late = late_draws(tweens, dur)
    if not late:
        return None
    return Flag(
        "drawing",
        f"{len(late)} element(s) still drawing at the exit (up to {max(late):.2f}s past the fade start)",
    )


def _short(s: str, n: int = 24) -> str:
    s = " ".join(str(s).split())
    return repr(s if len(s) <= n else s[: n - 1] + "…")


def _merge(flags: list[Flag]) -> list[Flag]:
    """One flag per code: the first message, plus how many more texts share it."""
    out: dict[str, list[Flag]] = {}
    for f in flags:
        out.setdefault(f.code, []).append(f)
    merged = []
    for code, fs in out.items():
        more = f" (+{len(fs) - 1} more)" if len(fs) > 1 else ""
        merged.append(Flag(code, fs[0].message + more))
    return merged
