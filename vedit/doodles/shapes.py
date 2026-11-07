"""The shape vocabulary of a scene spec: kind name -> drawing function, with how its parameters are written.

Every shape in a spec is a one-key mapping `{kind: {params}}`. `at: [x, y]` fills the function's first two
parameters (a centre, or the top-left corner for `rect`, `window`, `bubble`, `barchart`); `lw` is a line width
as a multiple of the pack's weight; colours are tokens (ink, accent, soft, warn) or CSS colours. Primitives
(`line`, `poly`, `rect`, `oval`, `arc`, `circle`, `curve`) also take `fill` (opacity, or {opacity, color, dx,
dy}), `hatch` ({angle, gap, inset}), `stroke: false` (fill only) and the stroke options below.
"""

from __future__ import annotations

import inspect
import math

from vedit.doodles import icons, marks
from vedit.doodles.geom import arc as _arc
from vedit.doodles.geom import densify, ellipse, quad, rrect
from vedit.doodles.geom import poly as _poly

STROKE_OPTS = ("color", "lw", "amp", "bow", "double", "opacity", "stroke", "fill", "hatch")


def _paint(s, pts, closed, color="ink", lw=None, amp=1.9, bow=None, double=False, opacity=1.0, stroke=True,
           fill=None, hatch=None):  # fmt: skip
    if stroke:
        s.stroke(pts, color=color, w=lw, amp=amp, closed=closed, double=double, opacity=opacity, bow=bow)
    if fill:
        f = {"opacity": fill} if isinstance(fill, int | float) else dict(fill)
        s.fill(pts, **{k: tuple(v) if isinstance(v, list) else v for k, v in f.items()})
    if hatch:
        h = {} if hatch is True else dict(hatch)
        if "inset" in h:
            h["inset"] = tuple(h["inset"])
        s.hatch(pts, **h)


def line(s, pts, closed=False, **o):
    """A polyline through `pts` (two points: a straight stroke)."""
    _paint(s, densify([tuple(p) for p in pts]), closed, **o)


def poly(s, pts, **o):
    """A closed polygon through `pts`."""
    _paint(s, _poly([tuple(p) for p in pts]), True, **o)


def rect(s, x, y, w, h, r=18, **o):
    """Rounded rectangle; (x, y) is its top-left corner."""
    _paint(s, rrect(x, y, w, h, r), True, **o)


def oval(s, cx, cy, rx, ry=None, start=-2.2, **o):
    """Closed ellipse (circle when ry is omitted); start is where the pen begins (radians)."""
    _paint(s, ellipse(cx, cy, rx, rx if ry is None else ry, start=start), True, **o)


def arc(s, cx, cy, rx, ry=None, a0=0.0, a1=180.0, **o):
    """Open arc from angle a0 to a1 (degrees, 0 = right, 90 = down)."""
    _paint(s, _arc(cx, cy, rx, rx if ry is None else ry, math.radians(a0), math.radians(a1)), False, **o)


def circle(s, cx, cy, r, color="ink", lw=None, amp=1.9, double=False, fill=None):
    """Circle whose pen start varies a little (T `circle`)."""
    kw = {"color": color, "amp": amp, "double": double}
    if lw is not None:
        kw["w"] = lw
    marks.circle(s, cx, cy, r, **kw)
    if fill:
        s.fill(ellipse(cx, cy, r, r), opacity=fill)


def curve(s, a, via, b, dashed=False, color="ink", lw=None, amp=1.1):
    """Quadratic curve from a through the pull of `via` to b; dashed draws it as dashes."""
    pts = quad(tuple(a), tuple(via), tuple(b))
    if dashed:
        marks.dashes(s, pts, color=color, w=lw)
    else:
        s.stroke(pts, color=color, w=lw, amp=amp, bow=0)


def dot(s, cx, cy, r, color="ink"):
    s.dot(cx, cy, r, color=color)


def head(s, x, y, dir, size=26, color="ink", w=None):
    """Arrow head at (x, y) pointing along dir [dx, dy] (a unit vector; a longer one draws a bigger head, as T)."""
    marks.head(s, (x, y), (dir[0], dir[1]), size, color, w)


def arrow(s, a, b, bend=0.0, color="ink", w=None, size=26, both=False, dashed=False):
    marks.arrow(s, tuple(a), tuple(b), bend, color, w, size, both, dashed)


def burst(s, cx, cy, r0, r1, a0=189.0, a1=351.0, n=7, color="warn"):
    """Impact rays between a0 and a1 (degrees)."""
    marks.burst(s, cx, cy, r0, r1, math.radians(a0), math.radians(a1), n, color)


def crack(s, pts, color="warn"):
    marks.crack(s, pts, color)


def arc_arrow(s, cx, cy, rx, ry=None, a0=0.0, a1=270.0, color="soft", size=24, amp=1.0):
    marks.arc_arrow(s, cx, cy, rx, rx if ry is None else ry, a0, a1, color, size, amp)


# kind -> function. Order of parameters after `s` is what `at` fills (the first two).
KINDS = {
    "line": line, "poly": poly, "rect": rect, "oval": oval, "arc": arc, "circle": circle, "curve": curve,
    "dot": dot, "head": head, "arrow": arrow, "check": marks.check, "cross": marks.cross,
    "spark": marks.spark, "burst": burst, "crack": crack, "qmark": marks.qmark, "play": marks.play_tri,
    "trend": marks.trend, "arc_arrow": arc_arrow,
    "laptop": icons.laptop, "phone": icons.phone, "play_phone": icons.play_phone, "server": icons.server,
    "rack": icons.rack, "bot": icons.bot, "person": icons.person, "people": icons.people,
    "bubble": icons.bubble, "megaphone": icons.megaphone, "key": icons.key, "clock": icons.clock,
    "gear": icons.gear, "telegram": icons.telegram, "window": icons.window, "envelope": icons.envelope,
    "coin": icons.coin, "shop": icons.shop, "stopwatch": icons.stopwatch, "diamond": icons.diamond,
    "barchart": icons.barchart, "plug": icons.plug, "gift": icons.gift, "hardhat": icons.hardhat,
    "gauge": icons.gauge, "tag": icons.tag, "social": icons.social, "ngon": icons.ngon,
}  # fmt: skip
LINE_W = {"head", "arrow", "check", "cross", "trend"}  # their `w` is a line width: written as `lw`
LINE_LW = {"bubble", "ngon", "line", "poly", "rect", "oval", "arc", "circle", "curve"}  # `lw` passes as px
SPECIAL = {"at", "id", "jitter"}  # spec keys every shape takes (jitter: random offset px, repeated `at`)


def params(kind: str) -> tuple[list[str], set[str], bool]:
    """(positional names `at` fills or that are required, every accepted key, whether `at` applies)."""
    fn = KINDS[kind]
    sig = list(inspect.signature(fn).parameters.values())[1:]
    names = [p.name for p in sig if p.kind is not p.VAR_KEYWORD]
    if any(p.kind is p.VAR_KEYWORD for p in sig):
        names += list(STROKE_OPTS)
    required = [p.name for p in sig if p.default is p.empty and p.kind is not p.VAR_KEYWORD]
    at_ok = len(required) >= 2 and required[0] in ("cx", "x") and required[1] in ("cy", "y")
    accepted = set(names) | SPECIAL
    if kind in LINE_W:
        accepted = (accepted - {"w"}) | {"lw"}
    if not at_ok:
        accepted.discard("at")
    return required, accepted, at_ok


def call(s, kind: str, p: dict) -> None:
    """Draw one shape (its params already validated)."""
    fn = KINDS[kind]
    kw = {k: v for k, v in p.items() if k not in SPECIAL}
    if "lw" in kw:
        px = kw.pop("lw") * s.sw
        kw["w" if kind in LINE_W else "lw"] = px
    for k in ("heights",):
        if isinstance(kw.get(k), list):
            kw[k] = tuple(kw[k])
    ats = p.get("at")
    if ats is None:
        fn(s, **kw)
        return
    first, second = params(kind)[0][:2]
    pts = ats if isinstance(ats[0], list | tuple) else [ats]
    for x, y in pts:
        if p.get("jitter"):
            j = float(p["jitter"])
            x, y = x + s.rng.uniform(-j, j), y + s.rng.uniform(-j, j)
        fn(s, **{first: x, second: y}, **kw)
