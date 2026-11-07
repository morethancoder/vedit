"""Aspects, platform placements and their HUD safe zones (`platforms.json`, from
docs/research/platform-safe-zones.md). Every phase-11 leaf reads geometry from here, never from constants.

Insets are pixels on the placement's own canvas; `safe_box` scales them to any canvas of the same aspect.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from fractions import Fraction
from functools import cache
from importlib import resources

from vedit.report import VeditError

# aspect -> default canvas (short side 1080; the 16:9 master renders at 4K from the same composition)
ASPECTS: dict[str, tuple[int, int]] = {
    "16:9": (1920, 1080),
    "9:16": (1080, 1920),
    "4:5": (1080, 1350),
    "1:1": (1080, 1080),
    "3:4": (1080, 1440),
    "2:3": (1080, 1620),
}
EDGES = ("top", "bottom", "left", "right")


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float

    @property
    def x1(self) -> float:
        return self.x + self.w

    @property
    def y1(self) -> float:
        return self.y + self.h

    def overlap(self, o: Box) -> float:
        """Area shared with `o` (0 when apart)."""
        w = min(self.x1, o.x1) - max(self.x, o.x)
        h = min(self.y1, o.y1) - max(self.y, o.y)
        return max(0.0, w) * max(0.0, h)

    def inside(self, o: Box, tol: float = 0.5) -> bool:
        return self.x >= o.x - tol and self.y >= o.y - tol and self.x1 <= o.x1 + tol and self.y1 <= o.y1 + tol

    def as_dict(self) -> dict:
        return {"x": round(self.x, 1), "y": round(self.y, 1), "w": round(self.w, 1), "h": round(self.h, 1)}


def ratio(aspect: str) -> Fraction:
    try:
        w, h = (int(x) for x in aspect.split(":"))
        return Fraction(w, h)
    except (ValueError, ZeroDivisionError) as e:
        raise VeditError(f"aspect {aspect!r}: write it as W:H, e.g. 9:16", code="bad_input") from e


def canvas(aspect: str) -> tuple[int, int]:
    if aspect not in ASPECTS:
        raise VeditError(
            f"aspect {aspect!r} is not supported (one of {', '.join(ASPECTS)})", code="bad_input"
        )
    return ASPECTS[aspect]


@cache
def _data() -> dict:
    return json.loads(resources.files("vedit.formats").joinpath("platforms.json").read_text(encoding="utf-8"))


def platforms() -> dict[str, dict]:
    return _data()["platforms"]


def platform(pid: str) -> dict:
    p = platforms().get(pid)
    if p is None:
        raise VeditError(
            f"platform {pid!r} is unknown (one of {', '.join(platforms())})",
            next="vedit formats",
            code="bad_input",
        )
    return p


def _scale(pid: str, size: tuple[int, int]) -> tuple[float, float]:
    p = platform(pid)
    pw, ph = p["canvas"]
    if ratio(f"{size[0]}:{size[1]}") != ratio(f"{pw}:{ph}") and ratio(f"{size[0]}:{size[1]}") != ratio(
        p["aspect"]
    ):
        raise VeditError(
            f"{p['name']} is {p['aspect']}; a {size[0]}x{size[1]} frame does not fit it", code="bad_input"
        )
    return size[0] / pw, size[1] / ph


def insets(pid: str, size: tuple[int, int] | None = None) -> dict[str, float]:
    p = platform(pid)
    size = size or tuple(p["canvas"])
    sx, sy = _scale(pid, size)
    s = p["safe"]
    return {
        "top": s["top"] * sy,
        "bottom": s["bottom"] * sy,
        "left": s["left"] * sx,
        "right": s["right"] * sx,
    }


def safe_box(pids: list[str], size: tuple[int, int]) -> Box:
    """The area every listed platform leaves clear (strictest inset per edge). No platforms: the whole frame."""
    w, h = size
    ins = {e: 0.0 for e in EDGES}
    for pid in pids:
        for e, v in insets(pid, size).items():
            ins[e] = max(ins[e], v)
    return Box(ins["left"], ins["top"], w - ins["left"] - ins["right"], h - ins["top"] - ins["bottom"])


def clear_span(pids: list[str], size: tuple[int, int], y0: float, y1: float) -> tuple[float, float]:
    """(x0, x1) of the safe box over the rows [y0, y1], also clear of every named HUD region in those rows that
    sits against the left or right half (an action column reaches further in than the side inset)."""
    box = safe_box(pids, size)
    x0, x1 = box.x, box.x1
    w = size[0]
    for pid in pids:
        p = platform(pid)
        if not p["regions"]:
            continue
        for r in hud(pid, size):
            b = r["box"]
            if (
                b.y1 <= y0 or b.y >= y1 or b.w >= 0.9 * w
            ):  # outside the rows, or a full-width bar (top/bottom)
                continue
            if b.x + b.w / 2 > w / 2:
                x1 = min(x1, b.x)
            else:
                x0 = max(x0, b.x1)
    return x0, max(x0, x1)


def hud(pid: str, size: tuple[int, int]) -> list[dict]:
    """Named HUD regions scaled to `size`: the researched regions, else bars built from the insets."""
    p = platform(pid)
    sx, sy = _scale(pid, size)
    out = []
    for r in p["regions"]:
        if all(r.get(k) is not None for k in ("x", "y", "w", "h")):
            box = Box(r["x"] * sx, r["y"] * sy, r["w"] * sx, r["h"] * sy)
            out.append({"name": r["name"], "what": r.get("what", ""), "box": box})
    if not out:
        i, (w, h) = insets(pid, size), size
        bars = [
            ("top bar", Box(0, 0, w, i["top"])),
            ("bottom bar", Box(0, h - i["bottom"], w, i["bottom"])),
            ("left edge", Box(0, 0, i["left"], h)),
            ("right edge", Box(w - i["right"], 0, i["right"], h)),
        ]
        out = [{"name": n, "what": "", "box": b} for n, b in bars if b.w > 0 and b.h > 0]
    return out


def visible(src: str, dst: str) -> dict[str, float]:
    """What a centered full-frame crop from aspect `src` to `dst` keeps: fractions of the source width/height."""
    a, b = ratio(src), ratio(dst)
    if b <= a:
        return {"width": float(b / a), "height": 1.0}
    return {"width": 1.0, "height": float(a / b)}
