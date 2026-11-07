"""Doodle geometry (pure, T tools/doodles.py): every shape is a dense centre-line polyline, sketchified later.

`sketch` turns a centre line into a hand-drawn one (low-frequency wobble along the normal, a slight bow for open
strokes, an overshoot past the start for closed shapes). All randomness comes from the caller's seeded RNG, so
the same scene always gives the same strokes. T's numbers, kept as they were tuned.
"""

from __future__ import annotations

import itertools
import math

TAU = 2 * math.pi


def dist(a, b):
    return math.hypot(b[0] - a[0], b[1] - a[1])


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def densify(pts, step=2.0):
    out = [pts[0]]
    for a, b in itertools.pairwise(pts):
        n = max(1, int(dist(a, b) / step))
        out.extend(lerp(a, b, i / n) for i in range(1, n + 1))
    return out


def dedupe(pts):
    out = [pts[0]]
    for p in pts[1:]:
        if dist(p, out[-1]) > 0.05:
            out.append(p)
    return out


def seg(a, b):
    return densify([a, b])


def arc(cx, cy, rx, ry, a0, a1, step=2.0):
    n = max(3, int(abs(a1 - a0) * max(rx, ry) / step))
    return [
        (cx + rx * math.cos(a0 + (a1 - a0) * i / n), cy + ry * math.sin(a0 + (a1 - a0) * i / n))
        for i in range(n + 1)
    ]


def ellipse(cx, cy, rx, ry, start=-2.2):
    return arc(cx, cy, rx, ry, start, start + TAU)


def quad(a, c, b, step=2.0):
    approx = dist(a, c) + dist(c, b)
    n = max(8, int(approx / step))
    out = []
    for i in range(n + 1):
        t = i / n
        u = 1 - t
        out.append(
            (u * u * a[0] + 2 * u * t * c[0] + t * t * b[0], u * u * a[1] + 2 * u * t * c[1] + t * t * b[1])
        )
    return out


def rrect(x, y, w, h, r, tail=None):
    """Rounded rect perimeter, clockwise from the top-left. tail=(x_right, x_left, tip) puts a speech-bubble
    tail on the bottom edge (x_right > x_left, both on the bottom edge)."""
    r = min(r, w / 2, h / 2)
    p = densify([(x + r, y), (x + w - r, y)])
    p += arc(x + w - r, y + r, r, r, -math.pi / 2, 0)
    p += densify([(x + w, y + r), (x + w, y + h - r)])
    p += arc(x + w - r, y + h - r, r, r, 0, math.pi / 2)
    if tail:
        xr, xl, tip = tail
        p += densify([(x + w - r, y + h), (xr, y + h), tip, (xl, y + h), (x + r, y + h)])
    else:
        p += densify([(x + w - r, y + h), (x + r, y + h)])
    p += arc(x + r, y + h - r, r, r, math.pi / 2, math.pi)
    p += densify([(x, y + h - r), (x, y + r)])
    p += arc(x + r, y + r, r, r, math.pi, 1.5 * math.pi)
    return dedupe(p)


def poly(points, closed=True):
    pts = list(points) + ([points[0]] if closed else [])
    return dedupe(densify(pts))


def rot(v, ang):
    c, s = math.cos(ang), math.sin(ang)
    return (v[0] * c - v[1] * s, v[0] * s + v[1] * c)


def unit(a, b):
    d = dist(a, b) or 1.0
    return ((b[0] - a[0]) / d, (b[1] - a[1]) / d)


def plen(pts):
    return sum(dist(a, b) for a, b in itertools.pairwise(pts))


def pd(pts):
    head = f"M{pts[0][0]:.1f} {pts[0][1]:.1f}L"
    return head + " ".join(f"{x:.1f} {y:.1f}" for x, y in pts[1:])


def sketch(
    rng, pts, amp=1.6, closed=False, wave=(70, 260), overshoot=None, drift=None, bow=None, spacing=6.0
):
    """Hand-drawn version of a centre line: low-frequency wobble along the normal, a slight bow for open
    strokes, and for closed shapes an overshoot past the start that lands a few px off."""
    pts = dedupe(densify(pts, 2.0))
    if len(pts) < 2:
        return pts
    if closed:
        ov = rng.uniform(16, 30) if overshoot is None else overshoot
        acc, i = 0.0, 1
        while ov > 0 and acc < ov and i < len(pts):
            acc += dist(pts[i - 1], pts[i])
            pts.append(pts[i])
            i += 1
    s = [0.0]
    for a, b in itertools.pairwise(pts):
        s.append(s[-1] + dist(a, b))
    L = s[-1] or 1.0
    waves = [(amp * f * rng.uniform(0.7, 1.3), rng.uniform(*wave), rng.uniform(0, TAU)) for f in (0.62, 0.32)]
    waves.append((amp * 0.16, rng.uniform(16, 30), rng.uniform(0, TAU)))
    if closed:
        bowv = 0.0
        dr = rng.uniform(2.5, 5.0) * rng.choice((-1, 1)) if drift is None else drift
    else:
        bowv = rng.uniform(0.35, 1.0) * rng.choice((-1, 1)) * min(7.0, L * 0.022) if bow is None else bow
        dr = 0.0
    n = len(pts)
    out = []
    for i, (x, y) in enumerate(pts):
        a, b = pts[max(0, i - 1)], pts[min(n - 1, i + 1)]
        tx, ty = b[0] - a[0], b[1] - a[1]
        tl = math.hypot(tx, ty) or 1.0
        nx, ny = -ty / tl, tx / tl
        u = s[i] / L
        off = sum(A * math.sin(TAU * s[i] / lam + ph) for A, lam, ph in waves)
        if closed:
            off += dr * u
        else:
            env = min(1.0, s[i] / 14.0, (L - s[i]) / 14.0)
            off = off * env + bowv * math.sin(math.pi * u)
        out.append((x + nx * off, y + ny * off))
    res, last = [out[0]], 0
    for i in range(1, n):
        if s[i] - s[last] >= spacing:
            res.append(out[i])
            last = i
    if res[-1] != out[-1]:
        res.append(out[-1])
    return res


def hatch_segments(rng, shape, angle=-38, gap=15.0, inset=(4, 12)):
    """Parallel hatch lines clipped to a closed polygon (scanline in rotated space)."""
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)
    R = [(x * ca + y * sa, -x * sa + y * ca) for x, y in shape]
    ys = [p[1] for p in R]
    y = min(ys) + gap * rng.uniform(0.4, 0.8)
    segs = []
    while y < max(ys) - 2:
        xs = []
        for (x1, y1), (x2, y2) in zip(R, R[1:] + R[:1], strict=False):
            if (y1 <= y < y2) or (y2 <= y < y1):
                xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            xa, xb = xs[i] + rng.uniform(*inset), xs[i + 1] - rng.uniform(*inset)
            if xb - xa > 10:
                ya, yb = y + rng.uniform(-1.5, 1.5), y + rng.uniform(-1.5, 1.5)
                segs.append(((xa * ca - ya * sa, xa * sa + ya * ca), (xb * ca - yb * sa, xb * sa + yb * ca)))
        y += gap * rng.uniform(0.88, 1.12)
    return segs


def split_visible(pts, hidden):
    """Split a polyline into the runs where hidden(p) is False (for simple occlusion)."""
    runs, cur = [], []
    for p in densify(pts, 2.0):
        if hidden(p):
            if len(cur) > 3:
                runs.append(cur)
            cur = []
        else:
            cur.append(p)
    if len(cur) > 3:
        runs.append(cur)
    return runs


def r3(v):
    return round(v, 3)
