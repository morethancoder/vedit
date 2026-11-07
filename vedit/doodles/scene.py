"""A doodle scene being drawn (T tools/doodles.py `Scene`): SVG paths, hand-lettered labels and their timings.

Strokes are collected into groups (z-order units: fills under lines, optional idle float) and scheduled as pen
passes (`draw`). The result is data for the pack's `types/doodle.html`: the SVG, the label HTML and the timing
tables its script plays (T's draw-on motion lives in the template). Colours and line weight come from the
pack's doodle.yaml (`Style`); RNG is seeded by the caller, so a scene always draws the same.
"""

from __future__ import annotations

import html as _html
import math
import random
import re
from dataclasses import dataclass

from vedit.doodles.geom import ellipse, hatch_segments, pd, plen, r3, seg, sketch, split_visible

ARABIC = re.compile(r"[؀-ۿ]")
FADE_LEAD = 0.75  # everything is on screen this long before the end (T)


@dataclass
class Style:
    """A pack's doodle.yaml, resolved: line colours, weight, wobble and lettering."""

    ink: str = "#FAF9F5"  # main line colour (T IVORY)
    accent: str = "#FFD60A"  # fills, highlights (T VIOLET, yellow in the Telegram video)
    soft: str = "#FFE45C"  # secondary labels and marks (T LILAC)
    warn: str = "#FF7A59"  # errors, crosses (T WARM)
    width: float = 4.6  # main line weight at 1920x1080 (T SW)
    wobble: float = 1.0  # multiplies every stroke's wobble amplitude
    arabic_scale: float = 0.92  # Arabic lettering size against Latin (T: Aref Ruqaa runs large)

    def color(self, v) -> str:
        """A colour token (ink, accent, soft, warn) or a CSS colour as given."""
        if v is None:
            return self.ink
        v = {"ink": self.ink, "accent": self.accent, "soft": self.soft, "warn": self.warn}.get(v, v)
        return _html.escape(str(v), quote=True)


class Scene:
    def __init__(self, seed: int, dur: float, style: Style | None = None):
        self.dur = dur
        self.st = style or Style()
        self.sw = self.st.width
        self.rng = random.Random(seed)
        self.n = 0
        self.groups: list[dict] = []
        self.cur: dict = {}
        self.batch: list = []
        self.draws: list = []
        self.fades: list = []
        self.labs: list = []
        self.spins: list = []
        self.labels_html: list[str] = []
        self.group()

    def _id(self) -> int:
        self.n += 1
        return self.n

    # groups: z-order unit (fills under lines) and optional idle float
    def group(self, float_px=0.0) -> int:
        k = self._id()
        self.cur = {"k": k, "fills": [], "lines": [], "float": float_px, "end": 0.0}
        self.groups.append(self.cur)
        return k

    def use(self, k: int) -> None:
        """Add the next elements to an earlier group (keeps its z-order)."""
        self.cur = next(g for g in self.groups if g["k"] == k)

    def _path(self, pts, color, w, opacity, weight):
        k = self._id()
        L = plen(pts)
        D = math.ceil(L + 1)
        off = D + math.ceil(w) + 2
        attrs = f'class="dw k{k}" d="{pd(pts)}" stroke="{color}" stroke-width="{w:.1f}"'
        if opacity < 1:
            attrs += f' stroke-opacity="{opacity:.2f}"'
        self.cur["lines"].append(
            f'<path {attrs} style="stroke-dasharray:{D} {D + 60};stroke-dashoffset:{off}"/>'
        )
        self.batch.append(("s", k, off, L * weight, self.cur))
        return k

    def stroke(
        self,
        pts,
        color=None,
        w=None,
        amp=1.9,
        closed=False,
        double=False,
        weight=1.0,
        opacity=1.0,
        bow=None,
        hidden=None,
        wave=(60, 230),
    ):
        color = self.st.color(color)
        w = self.sw if w is None else w
        if hidden is not None:
            ks = [
                self.stroke(run, color, w, amp, False, double, weight, opacity, bow, None, wave)
                for run in split_visible(pts, hidden)
            ]
            return ks[0] if ks else None
        a = amp * self.st.wobble
        k = self._path(
            sketch(self.rng, pts, amp=a, closed=closed, bow=bow, wave=wave), color, w, opacity, weight
        )
        if double:
            self._path(
                sketch(self.rng, pts, amp=a * 1.5, closed=closed, wave=wave),
                color,
                w * 0.55,
                opacity * 0.5,
                weight * 0.3,
            )
        return k

    def fill(self, pts, color="accent", opacity=0.24, dx=8.0, dy=7.0, amp=2.2):
        sk = sketch(self.rng, pts, amp=amp * self.st.wobble, closed=True, overshoot=0, drift=0, spacing=8.0)
        sk = [(x + dx, y + dy) for x, y in sk]
        k = self._id()
        self.cur["fills"].append(
            f'<path class="fd k{k}" d="{pd(sk)}Z" fill="{self.st.color(color)}" fill-opacity="{opacity:.2f}" '
            'style="opacity:0"/>'
        )
        self.batch.append(("f", k, 0, 0, self.cur))
        return k

    def dot(self, cx, cy, r, color="ink"):
        return self.fill(ellipse(cx, cy, r, r), color=color, opacity=1.0, dx=0, dy=0, amp=min(0.5, r * 0.08))

    def hatch(self, shape, angle=-38, gap=15.0, color="accent", w=2.6, opacity=0.85, inset=(4, 12)):
        for a, b in hatch_segments(self.rng, shape, angle, gap, inset):
            self.stroke(seg(a, b), color=color, w=w, amp=0.5, weight=0.3, opacity=opacity)

    def draw(self, t, dur):
        """Schedule everything added since the last draw() as one pen pass across [t, t+dur]."""
        items, self.batch = self.batch, []
        deadline = self.dur - FADE_LEAD
        if t + dur > deadline:
            dur = max(0.35, min(dur, deadline - t))
            t = max(0.0, min(t, deadline - dur))
        total = sum(it[3] for it in items if it[0] == "s") or 1.0
        acc = 0.0
        for kind, k, off, wl, g in items:
            st = t + dur * acc / total
            if kind == "s":
                d = max(0.05, dur * wl / total)
                self.draws.append([k, off, r3(st), r3(d)])
                acc += wl
                end = st + d
            else:
                st = max(0.0, min(st, self.dur - 1.1))
                self.fades.append([k, r3(st), 0.45])
                end = st + 0.45
            g["end"] = max(g["end"], end)
        return t + dur

    def label(
        self, text, x, y, t, size=60, weight=700, color="ink", mono=False, anchor="middle", mode="w", d=None
    ):
        """Hand-lettered label. Arabic writes on right to left (RTL), Latin left to right; the pack's lettering
        fonts set each script (`.dz-t.ar`, `.dz-t`, `.dz-t.mono`). anchor: middle | start (left) | end (right)."""
        k = self._id()
        text = str(text)
        ar = bool(ARABIC.search(text))
        if ar and mode == "w":
            mode = "r"
        tr = {"middle": "translate(-50%,-50%)", "start": "translate(0,-50%)", "end": "translate(-100%,-50%)"}[
            anchor
        ]
        init = {"w": "clip-path:inset(-30% 100% -30% 0%)", "r": "clip-path:inset(-30% 0% -30% 100%)"}.get(
            mode, "opacity:0"
        )
        cls = "dz-t mono" if mono else ("dz-t ar" if ar else "dz-t")
        if ar:
            size = round(size * self.st.arabic_scale)
        rtl = ' dir="rtl"' if ar else ""
        self.labels_html.append(
            f'<div class="dz-lb" style="left:{x:.0f}px;top:{y:.0f}px;transform:{tr}">'
            f'<span class="{cls} k{k}"{rtl} style="font-size:{size}px;font-weight:{weight};'
            f'color:{self.st.color(color)};{init}">{_html.escape(text)}</span></div>'
        )
        if d is None:
            d = min(1.0, max(0.45, 0.28 + 0.04 * len(text)))
        deadline = self.dur - FADE_LEAD
        if t + d > deadline:
            d = max(0.35, min(d, deadline - t))
            t = max(0.0, min(t, deadline - d))
        self.labs.append([k, r3(t), r3(d), mode])
        return k

    def spin(self, k, cx, cy, rate, start):
        """Slow idle rotation of group k about (cx, cy) at rate deg/s until the fade-out."""
        start = max(start, next(g for g in self.groups if g["k"] == k)["end"])
        span = self.dur - 0.6 - start
        if span >= 0.8:
            self.spins.append([k, f"{cx:.0f} {cy:.0f}", round(rate * span, 2), r3(start), r3(span)])

    # ---- output ----

    def svg(self) -> str:
        groups = []
        for g in self.groups:
            if not g["fills"] and not g["lines"]:
                continue
            inner = ""
            if g["fills"]:
                inner += "<g>" + "".join(g["fills"]) + "</g>"
            if g["lines"]:
                inner += "<g>" + "".join(g["lines"]) + "</g>"
            groups.append(f'<g class="g{g["k"]}">{inner}</g>')
        return (
            '<svg class="dz" viewBox="0 0 1920 1080" width="1920" height="1080" '
            'xmlns="http://www.w3.org/2000/svg">' + "".join(groups) + "</svg>"
        )

    def floats(self) -> list:
        out = []
        for g in self.groups:
            st, en = g["end"] + 0.15, self.dur - 0.6
            if g["float"] and (g["fills"] or g["lines"]) and en - st > 1.2:
                out.append([g["k"], r3(st), r3(en - st), g["float"]])
        return out
