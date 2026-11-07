"""Doodle marks (T tools/doodles.py + doodles_tele.py helpers): arrows, heads, dashes, ticks, crosses, sparks,
bursts, question marks. Each adds strokes to the scene's current pen pass. `w` is a line width in px (None =
the pack's weight); colours are tokens (ink, accent, soft, warn) or CSS colours.
"""

from __future__ import annotations

import itertools
import math

from vedit.doodles.geom import TAU, arc, dedupe, densify, dist, ellipse, lerp, poly, quad, rot, seg, unit


def _w(s, w, k=1.0):
    return s.sw * k if w is None else w


def head(s, tip, direction, size=26, color="ink", w=None, spread=28):
    """Two-stroke arrow head at tip, pointing along direction (unit vector)."""
    w = _w(s, w)
    back = (-direction[0], -direction[1])
    for sgn in (-1, 1):
        v = rot(back, math.radians(spread * sgn + s.rng.uniform(-4, 4)))
        ln = size * s.rng.uniform(0.9, 1.08)
        s.stroke(seg(tip, (tip[0] + v[0] * ln, tip[1] + v[1] * ln)), color=color, w=w, amp=0.6, bow=0)


def arrow(s, a, b, bend=0.0, color="ink", w=None, size=26, both=False, dashed=False):
    """Arrow from a to b; bend pushes the curve sideways (px, + = to the left of travel)."""
    w = _w(s, w)
    u = unit(a, b)
    nrm = (u[1], -u[0])
    mid = lerp(a, b, 0.5)
    c = (mid[0] + nrm[0] * bend, mid[1] + nrm[1] * bend)
    pts = quad(a, c, b)
    if dashed:
        dashes(s, pts, color=color, w=w)
    else:
        s.stroke(pts, color=color, w=w, amp=1.1, bow=0)
    head(s, b, unit(c, b) if bend else u, size, color, w)
    if both:
        head(s, a, unit(c, a) if bend else (-u[0], -u[1]), size, color, w)


def dashes(s, pts, dash=22.0, gap=15.0, color="ink", w=None):
    w = _w(s, w)
    pts = densify(pts, 2.0)
    run, acc, on = [pts[0]], 0.0, True
    for a, b in itertools.pairwise(pts):
        acc += dist(a, b)
        if on:
            run.append(b)
        if on and acc >= dash:
            if len(run) > 2:
                s.stroke(run, color=color, w=w, amp=0.4, bow=0)
            on, acc, run = False, 0.0, []
        elif not on and acc >= gap:
            on, acc, run = True, 0.0, [b]
    if on and len(run) > 4:
        s.stroke(run, color=color, w=w, amp=0.4, bow=0)


def check(s, cx, cy, k, color="ink", w=None):
    pts = densify([(cx - 0.5 * k, cy), (cx - 0.14 * k, cy + 0.4 * k), (cx + 0.55 * k, cy - 0.48 * k)])
    s.stroke(pts, color=color, w=_w(s, w, 1.3), amp=0.9, bow=0)


def cross(s, cx, cy, k, color="warn", w=None):
    w = _w(s, w, 1.25)
    s.stroke(seg((cx - k, cy - k), (cx + k, cy + k)), color=color, w=w, amp=0.8)
    s.stroke(seg((cx + k, cy - k * 0.95), (cx - k * 1.05, cy + k)), color=color, w=w, amp=0.8)


def circle(s, cx, cy, r, **kw):
    kw.setdefault("closed", True)
    return s.stroke(ellipse(cx, cy, r, r, start=-2.2 + s.rng.uniform(-0.4, 0.4)), **kw)


def spark(s, cx, cy, R, color="accent", n=10):
    """The Claude spark: ~10 uneven rounded rays drawn outward from the centre."""
    w = max(4.0, R * 0.2)
    for i in range(n):
        a = -math.pi / 2 + TAU * i / n + math.radians(s.rng.uniform(-5, 5))
        ln = R * (1.0 if i % 2 == 0 else 0.74) * s.rng.uniform(0.86, 1.0)
        a0 = (cx + math.cos(a) * R * 0.03, cy + math.sin(a) * R * 0.03)
        a1 = (cx + math.cos(a) * ln, cy + math.sin(a) * ln)
        s.stroke(seg(a0, a1), color=color, w=w, amp=0.5, bow=s.rng.uniform(-1.5, 1.5))


def burst(s, cx, cy, r0, r1, a0, a1, n=7, color="warn"):
    """Impact rays between angles a0..a1 (radians), alternating long and short."""
    for i in range(n):
        a = a0 + (a1 - a0) * i / (n - 1)
        rr1 = r1 * (1.0 if i % 2 == 0 else 0.82)
        p0 = (cx + math.cos(a) * r0, cy + math.sin(a) * r0)
        s.stroke(
            seg(p0, (cx + math.cos(a) * rr1, cy + math.sin(a) * rr1)), color=color, w=s.sw * 1.1, amp=0.6
        )


def crack(s, pts, color="warn"):
    s.stroke(densify([tuple(p) for p in pts]), color=color, w=s.sw * 1.2, amp=0.5, bow=0)


def qmark(s, cx, cy, r, color="accent"):
    pts = arc(cx, cy, r, r, math.pi, TAU + 0.5)
    pts += quad(pts[-1], (cx + r * 0.1, cy + r * 1.2), (cx, cy + r * 1.7))
    s.stroke(dedupe(pts), color=color, w=s.sw * 1.7, amp=1.0, bow=0)
    s.dot(cx, cy + r * 2.25, r * 0.17, color=color)


def play_tri(s, cx, cy, k, color="accent"):
    tri = [(cx - 0.4 * k, cy - 0.5 * k), (cx - 0.4 * k, cy + 0.5 * k), (cx + 0.55 * k, cy)]
    s.stroke(poly(tri), closed=True, color=color, w=s.sw * 0.9, amp=0.5)
    s.fill(poly(tri), color=color, opacity=0.35, dx=3, dy=3)


def trend(s, x, y, length, rise, wiggle=11.0, color="accent", w=None, size=32):
    """A rising chart line from (x, y) over w px, up by `rise`, with a small wiggle, and an arrow head (T chart)."""
    pts = []
    for i in range(61):
        u = i / 60
        pts.append((x + length * u, y - rise * u**1.6 + wiggle * math.sin(u * 15) * math.sin(math.pi * u)))
    w = s.sw * 1.5 if w is None else w
    s.stroke(pts, color=color, w=w, amp=0.5, bow=0)
    head(s, pts[-1], unit(pts[-4], pts[-1]), size, color=color, w=w)


def arc_arrow(s, cx, cy, rx, ry, a0, a1, color="soft", size=24, amp=1.0):
    """An arc from angle a0 to a1 (degrees) with a head at its end (T bot `workflow`)."""
    pts = arc(cx, cy, rx, ry, math.radians(a0), math.radians(a1))
    s.stroke(pts, color=color, amp=amp, bow=0)
    head(s, pts[-1], unit(pts[-4], pts[-1]), size, color=color)
