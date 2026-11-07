"""Doodle icons (T tools/doodles.py + doodles_tele.py, T's numbers): laptop, phone, server, bot, person, people,
bubble, megaphone, key, clock, gear, telegram plane, window, envelope, coin, shop, stopwatch, diamond, bar chart,
plug, gift, hard hat, gauge, tag, social marks. Each adds strokes to the scene's current pen pass; (cx, cy) is
the centre unless the docstring says otherwise.
"""

from __future__ import annotations

import math

from vedit.doodles.geom import TAU, arc, dedupe, densify, dist, ellipse, poly, quad, rrect, seg
from vedit.doodles.marks import circle, play_tri, spark


def laptop(s, cx, cy, w, prompt=True, fill=False):
    """Laptop with a terminal; (cx, cy) is the screen centre. Returns the screen box."""
    SW = s.sw
    h = w * 0.62
    x0, y0 = cx - w / 2, cy - h / 2
    scr = rrect(x0, y0, w, h, 18)
    s.stroke(scr, closed=True)
    if fill:
        s.fill(scr, opacity=0.16)
    bw, bh = w * 1.2, 24
    s.stroke(rrect(cx - bw / 2, y0 + h + 8, bw, bh, 11), closed=True)
    s.stroke(
        seg((cx - w * 0.09, y0 + h + 8 + bh * 0.42), (cx + w * 0.09, y0 + h + 8 + bh * 0.42)),
        w=SW * 0.7,
        amp=0.4,
    )
    if prompt:
        px, py, k = x0 + w * 0.12, y0 + h * 0.24, w * 0.045
        s.stroke(seg((px, py), (px + w * 0.42, py)), color="accent", w=SW * 0.9, amp=0.8)
        s.stroke(
            seg((px, py + h * 0.17), (px + w * 0.28, py + h * 0.17)), color="accent", w=SW * 0.9, amp=0.8
        )
        cy2 = py + h * 0.38
        s.stroke(densify([(px, cy2 - k), (px + k * 1.05, cy2), (px, cy2 + k)]), w=SW, amp=0.5, bow=0)
        s.stroke(seg((px + k * 2.0, cy2 + k), (px + k * 3.6, cy2 + k)), w=SW, amp=0.4)
    return (x0, y0, w, h)


def phone(s, cx, cy, w, h):
    s.stroke(rrect(cx - w / 2, cy - h / 2, w, h, w * 0.17), closed=True)
    s.stroke(seg((cx - w * 0.12, cy - h / 2 + 20), (cx + w * 0.12, cy - h / 2 + 20)), w=s.sw * 0.8, amp=0.3)
    s.stroke(seg((cx - w * 0.16, cy + h / 2 - 18), (cx + w * 0.16, cy + h / 2 - 18)), w=s.sw * 0.8, amp=0.3)


def play_phone(s, cx, cy, w, h):
    phone(s, cx, cy, w, h)
    play_tri(s, cx, cy, w * 0.42)


def server(s, cx, cy, w, unit_h=84, units=3, gap=14, fill=True):
    """Rack server / VPS: stacked units with two lights and vent lines. Returns (top, bottom)."""
    total = units * unit_h + (units - 1) * gap
    y = cy - total / 2
    x0 = cx - w / 2
    for i in range(units):
        box = rrect(x0, y, w, unit_h, 14)
        s.stroke(box, closed=True)
        if fill and i == 0:
            s.fill(box, opacity=0.2)
        ly = y + unit_h / 2
        s.dot(x0 + 34, ly, 8.5, color="accent")
        s.dot(x0 + 64, ly, 8.5, color="soft" if i % 2 == 0 else "ink")
        for j in range(3):
            vx = x0 + w - 40 - j * 22
            s.stroke(seg((vx, ly - unit_h * 0.2), (vx, ly + unit_h * 0.2)), w=s.sw * 0.75, amp=0.3)
        y += unit_h + gap
    return (cy - total / 2, cy + total / 2)


def rack(s, cx, cy, w=250, h=340):
    """Tall server cabinet with two lit units (C harness); the spark sits in its lower half."""
    x0, y0 = cx - w / 2, cy - h / 2
    body = rrect(x0, y0, w, h, 22)
    s.stroke(body, closed=True)
    s.fill(body, opacity=0.18)
    for yy in (y0 + 72, y0 + 144):
        s.stroke(seg((x0 + 6, yy), (x0 + w - 6, yy)), amp=0.8)
    for i, ly in enumerate((y0 + 36, y0 + 108)):
        s.dot(x0 + 34, ly, 8.5, color="accent")
        s.dot(x0 + 62, ly, 8.5, color="soft" if i == 0 else "ink")
        for j in range(3):
            vx = x0 + w - 36 - j * 20
            s.stroke(seg((vx, ly - 14), (vx, ly + 14)), w=s.sw * 0.75, amp=0.3)


def bot(s, cx, cy, w, h, face="eyes", fill=True):
    """Friendly bot: rounded-square head, ears, antenna; face = 'eyes' | 'spark' | None."""
    x0, y0 = cx - w / 2, cy - h / 2
    ew, eh = w * 0.08, h * 0.34
    hd = rrect(x0, y0, w, h, w * 0.24)
    s.stroke(hd, closed=True)
    if fill:
        s.fill(hd, opacity=0.24)
    s.stroke(rrect(x0 - ew, cy - eh / 2, ew + 4, eh, 6), closed=True, amp=0.8)
    s.stroke(rrect(x0 + w - 4, cy - eh / 2, ew + 4, eh, 6), closed=True, amp=0.8)
    at = h * 0.26
    s.stroke(seg((cx, y0), (cx + 2, y0 - at)), w=s.sw, amp=0.5)
    circle(s, cx + 2, y0 - at - 11, 11, amp=0.5)
    if face == "eyes":
        s.dot(cx - w * 0.2, cy - h * 0.06, w * 0.055)
        s.dot(cx + w * 0.2, cy - h * 0.06, w * 0.055)
        s.stroke(
            arc(cx, cy + h * 0.1, w * 0.13, h * 0.09, 0.35, math.pi - 0.35), w=s.sw * 0.9, amp=0.4, bow=0
        )
    elif face == "spark":
        spark(s, cx, cy + h * 0.03, min(w, h) * 0.3)


def person(s, cx, cy, size, hidden=None, hatch=False, fill=False, color="ink"):
    """Head + shoulders bust; (cx, cy) is the shoulder top. Spans y from cy-0.75s to cy+0.62s."""
    hr = 0.3 * size
    hc = (cx, cy - 0.45 * size)
    rx, ry = 0.66 * size, 0.62 * size
    by = cy + ry
    body = dedupe(arc(cx, by, rx, ry, math.pi, TAU) + densify([(cx + rx, by), (cx - rx, by)]))
    s.stroke(
        ellipse(hc[0], hc[1], hr, hr, start=-2.4 + s.rng.uniform(-0.3, 0.3)),
        closed=hidden is None,
        hidden=hidden,
        color=color,
    )
    s.stroke(body, closed=hidden is None, hidden=hidden, color=color)
    if fill:
        s.fill(body, opacity=0.24)
    if hatch:
        s.hatch(arc(cx, by, rx, ry, math.pi, TAU), gap=14)


def person_region(cx, cy, size, pad=9.0):
    hr = 0.3 * size + pad
    hc = (cx, cy - 0.45 * size)
    rx, ry = 0.66 * size + pad, 0.62 * size + pad
    by = cy + 0.62 * size

    def inside(p):
        if dist(p, hc) < hr:
            return True
        if p[1] <= by + pad and ((p[0] - cx) / rx) ** 2 + ((p[1] - by) / ry) ** 2 < 1:
            return True
        return abs(p[0] - cx) < rx and by <= p[1] <= by + pad

    return inside


def people(s, cx, cy, size):
    """Group of three: front person plus two behind, back lines cut where the front one covers them."""
    front = person_region(cx, cy, size)
    bs = size * 0.84
    for dx in (-0.78, 0.78):
        person(s, cx + dx * size, cy - 0.16 * size, bs, hidden=front)
    person(s, cx, cy, size, fill=True)


def bubble(s, x, y, w, h, side="left", color="ink", fill=False, lw=None):
    """Speech bubble; (x, y) is its top-left corner, the tail on the bottom edge at `side`."""
    r = min(22, h * 0.45)
    if side == "left":
        tail = (x + 48, x + 22, (x + 10, y + h + 17))
    else:
        tail = (x + w - 22, x + w - 48, (x + w - 10, y + h + 17))
    pts = rrect(x, y, w, h, r, tail=tail)
    s.stroke(pts, closed=True, color=color, w=s.sw if lw is None else lw, amp=1.0)
    if fill:
        s.fill(pts, opacity=0.22, dx=5, dy=5)
    return pts


def megaphone(s, cx, cy, size):
    """Megaphone pointing right with sound waves."""
    nx, wx = cx - 0.5 * size, cx + 0.42 * size
    nh, wh = 0.2 * size, 0.52 * size
    s.stroke(rrect(nx - 0.2 * size, cy - 0.16 * size, 0.2 * size + 4, 0.32 * size, 7), closed=True, amp=0.8)
    cone = [(nx, cy - nh), (wx, cy - wh), (wx, cy + wh), (nx, cy + nh)]
    s.stroke(poly(cone), closed=True)
    s.hatch(cone, angle=-50, gap=16)
    handle = [
        (cx - 0.22 * size, cy + 0.27 * size),
        (cx - 0.3 * size, cy + 0.62 * size),
        (cx - 0.14 * size, cy + 0.62 * size),
        (cx - 0.08 * size, cy + 0.33 * size),
    ]
    s.stroke(densify(handle), amp=0.6, bow=0)
    for rr in (0.2, 0.42):
        s.stroke(
            arc(wx, cy, (0.22 + rr) * size, (0.55 + rr) * size, -0.55, 0.55), w=s.sw * 0.9, amp=0.6, bow=0
        )


def key(s, cx, cy, size=1.0):
    """Horizontal key, ring on the left. (cx, cy) is the shaft line centre."""
    R = 38 * size
    rx = cx - 70 * size
    ring = ellipse(rx, cy, R, R)
    s.stroke(ring, closed=True)
    s.hatch(ring, angle=40, gap=13)
    circle(s, rx - 6 * size, cy, 10 * size, w=s.sw * 0.9, amp=0.4)
    x1, x2 = rx + R - 2, cx + 110 * size
    t1, t2, t3, t4 = cx + 92 * size, cx + 74 * size, cx + 58 * size, cx + 42 * size
    hh = 9 * size
    pts = [(x1, cy - hh), (x2, cy - hh), (x2, cy + hh), (t1, cy + hh), (t1, cy + hh + 24 * size)]
    pts += [(t2, cy + hh + 24 * size), (t2, cy + hh), (t3, cy + hh), (t3, cy + hh + 16 * size)]
    pts += [(t4, cy + hh + 16 * size), (t4, cy + hh), (x1, cy + hh)]
    s.stroke(densify(pts), amp=0.8, bow=0)


def clock(s, cx, cy, R):
    face = ellipse(cx, cy, R, R)
    s.stroke(face, closed=True, double=True)
    s.fill(face, opacity=0.18)
    for i in range(4):
        a = -math.pi / 2 + i * math.pi / 2
        p0 = (cx + math.cos(a) * R * 0.74, cy + math.sin(a) * R * 0.74)
        s.stroke(seg(p0, (cx + math.cos(a) * R * 0.88, cy + math.sin(a) * R * 0.88)), w=s.sw * 0.9, amp=0.3)
    up = -math.pi / 2
    s.stroke(seg((cx, cy), (cx + math.cos(up) * R * 0.62, cy + math.sin(up) * R * 0.62)), amp=0.5)
    s.stroke(seg((cx, cy), (cx + math.cos(0.45) * R * 0.45, cy + math.sin(0.45) * R * 0.45)), amp=0.5)
    s.dot(cx, cy, 6.5)


def gear(s, cx, cy, R, n=8, color="ink"):
    rin = R * 0.78
    step = TAU / n
    pts = []
    for i in range(n):
        a0 = i * step - math.pi / 2
        pts += arc(cx, cy, rin, rin, a0, a0 + 0.42 * step)
        pts += arc(cx, cy, R, R, a0 + 0.5 * step, a0 + 0.9 * step)
    pts.append(pts[0])
    shape = dedupe(densify(pts))
    s.stroke(shape, closed=True, color=color)
    s.fill(shape, opacity=0.22, dx=6, dy=5)
    circle(s, cx, cy, R * 0.32, color=color)


def telegram(s, cx, cy, R):
    """Telegram paper plane inside a circle."""
    w = max(3.0, min(s.sw, R * 0.09))
    circle(s, cx, cy, R, w=w * 1.15, amp=0.8)

    def P(x, y):
        return (cx + x * R, cy + y * R)

    s.stroke(poly([P(-0.5, 0.02), P(0.44, -0.4), P(0.26, 0.42), P(-0.02, 0.2)]), closed=True, w=w, amp=0.4)
    s.stroke(seg(P(-0.02, 0.2), P(0.24, -0.1)), w=w, amp=0.3, bow=0)


def window(s, x, y, w, h, bar=46):
    """App window; (x, y) is its top-left corner."""
    s.stroke(rrect(x, y, w, h, 20), closed=True)
    s.stroke(seg((x + 4, y + bar), (x + w - 4, y + bar)), amp=0.8)
    for i in range(3):
        s.dot(x + 30 + i * 26, y + bar / 2, 7, color="soft")


def envelope(s, cx, cy, w, color="ink"):
    h = w * 0.68
    x0, y0 = cx - w / 2, cy - h / 2
    s.stroke(rrect(x0, y0, w, h, 8), closed=True, color=color, w=s.sw * 0.8, amp=0.7)
    flap = densify([(x0 + 5, y0 + 5), (cx, cy + h * 0.1), (x0 + w - 5, y0 + 5)])
    s.stroke(flap, color=color, w=s.sw * 0.7, amp=0.4, bow=0)


def coin(s, cx, cy, R):
    f = ellipse(cx, cy, R, R)
    s.stroke(f, closed=True, double=True)
    s.fill(f, opacity=0.25)
    circle(s, cx, cy, R * 0.76, w=s.sw * 0.7, amp=0.5)


def shop(s, cx, cy, w):
    h = w * 0.95
    y0 = cy - h / 2
    ay = y0 + 0.3 * h
    awn = [(cx - w / 2, ay), (cx - 0.38 * w, y0), (cx + 0.38 * w, y0), (cx + w / 2, ay)]
    s.stroke(poly(awn), closed=True)
    s.fill(poly(awn), opacity=0.24)
    s.hatch(awn, angle=90, gap=24, inset=(3, 6))
    for i in range(4):
        s.stroke(
            arc(cx - w / 2 + (i + 0.5) * w / 4, ay, w / 8, w / 8 * 0.8, 0, math.pi),
            w=s.sw * 0.9,
            amp=0.4,
            bow=0,
        )
    walls = [
        (cx - 0.42 * w, ay + 14),
        (cx - 0.42 * w, y0 + h),
        (cx + 0.42 * w, y0 + h),
        (cx + 0.42 * w, ay + 14),
    ]
    s.stroke(poly(walls, closed=False), amp=0.9, bow=0)
    s.stroke(rrect(cx - 0.12 * w, y0 + h - 0.42 * h, 0.24 * w, 0.42 * h, 8), closed=True, w=s.sw * 0.9)


def stopwatch(s, cx, cy, R):
    f = ellipse(cx, cy, R, R)
    s.stroke(f, closed=True, double=True)
    s.fill(f, opacity=0.18)
    s.stroke(seg((cx, cy - R), (cx, cy - R - 16)), amp=0.3)
    s.stroke(rrect(cx - 18, cy - R - 32, 36, 16, 6), closed=True, w=s.sw * 0.9)
    s.stroke(seg((cx + R * 0.72, cy - R * 0.72), (cx + R * 0.9, cy - R * 0.9)), w=s.sw * 0.9, amp=0.3)


def diamond(s, cx, cy, w, h, fill=True):
    pts = [(cx, cy - h / 2), (cx + w / 2, cy), (cx, cy + h / 2), (cx - w / 2, cy)]
    s.stroke(poly(pts), closed=True)
    if fill:
        s.fill(poly(pts), opacity=0.2)


def barchart(s, x, y, w, h, heights=(0.25, 0.45, 0.7, 1.0)):
    """Axes and rising bars; (x, y) is the top of the y axis."""
    s.stroke(densify([(x, y), (x, y + h), (x + w, y + h)]), amp=0.8, bow=0)
    n = len(heights)
    bw = w / (n * 1.6)
    for i, hh in enumerate(heights):
        bx = x + 14 + i * (w - 20) / n
        bh = (h - 14) * hh
        bar = rrect(bx, y + h - 6 - bh, bw, bh, 6)
        s.stroke(bar, closed=True, w=s.sw * 0.9)
        s.fill(bar, opacity=0.3, dx=4, dy=4)


def plug(s, cx, cy, size):
    body = rrect(cx - 0.35 * size, cy - 0.4 * size, 0.7 * size, 0.8 * size, 16)
    s.stroke(body, closed=True)
    s.fill(rrect(cx - 0.35 * size, cy - 0.4 * size, 0.7 * size, 0.8 * size, 16), opacity=0.22)
    for dy in (-0.2, 0.2):
        s.stroke(seg((cx - 0.35 * size, cy + dy * size), (cx - 0.72 * size, cy + dy * size)), amp=0.5)
    s.stroke(
        quad((cx + 0.35 * size, cy), (cx + 0.6 * size, cy + 0.2 * size), (cx + 0.9 * size, cy)),
        amp=0.6,
        bow=0,
    )


def gift(s, cx, cy, w):
    box = rrect(cx - w / 2, cy - 0.1 * w, w, 0.6 * w, 8)
    s.stroke(box, closed=True)
    s.fill(box, opacity=0.22)
    s.stroke(rrect(cx - 0.56 * w, cy - 0.3 * w, 1.12 * w, 0.2 * w, 8), closed=True)
    s.stroke(seg((cx, cy - 0.1 * w), (cx, cy + 0.5 * w)), color="accent", amp=0.5)
    for sg in (-1, 1):
        bow = ellipse(cx + sg * 0.16 * w, cy - 0.42 * w, 0.15 * w, 0.1 * w)
        s.stroke(bow, closed=True, color="accent", w=s.sw * 0.9, amp=0.5)


def hardhat(s, cx, cy, w):
    dome = arc(cx, cy, w / 2, w * 0.46, math.pi, TAU)
    s.stroke(dedupe(dome + densify([(cx + w / 2, cy), (cx - w / 2, cy)])), closed=True)
    s.fill(dome, opacity=0.3)
    s.stroke(seg((cx - 0.64 * w, cy + 4), (cx + 0.64 * w, cy + 4)), amp=0.6)
    s.stroke(seg((cx, cy - 0.44 * w), (cx, cy - 0.12 * w)), w=s.sw * 0.9, amp=0.3)


def gauge(s, cx, cy, R):
    s.stroke(dedupe(arc(cx, cy, R, R, math.pi, TAU) + densify([(cx + R, cy), (cx - R, cy)])), closed=True)
    for i in range(1, 6):
        a = math.pi + math.pi * i / 6
        p0 = (cx + math.cos(a) * R * 0.86, cy + math.sin(a) * R * 0.86)
        s.stroke(seg(p0, (cx + math.cos(a) * R * 0.97, cy + math.sin(a) * R * 0.97)), w=s.sw * 0.8, amp=0.2)
    s.stroke(
        arc(cx, cy, R * 0.74, R * 0.74, TAU - 1.0, TAU - 0.05), color="warn", w=s.sw * 1.8, amp=0.5, bow=0
    )
    a = -0.38
    s.stroke(
        seg((cx, cy), (cx + math.cos(a) * R * 0.78, cy + math.sin(a) * R * 0.78)),
        w=s.sw * 1.1,
        amp=0.4,
        bow=0,
    )
    s.dot(cx, cy, 9)


def tag(s, cx, cy, w, h):
    pts = [(cx - w / 2 + 28, cy - h / 2), (cx + w / 2, cy - h / 2), (cx + w / 2, cy + h / 2)]
    pts += [(cx - w / 2 + 28, cy + h / 2), (cx - w / 2, cy)]
    s.stroke(poly(pts), closed=True, w=s.sw * 0.9)
    s.fill(poly(pts), opacity=0.2, dx=4, dy=4)
    circle(s, cx - w / 2 + 28, cy, 6, w=s.sw * 0.7, amp=0.2)


def social(s, cx, cy, kind="x"):
    """Small platform mark: tiktok | instagram | x."""
    x, y, SW = cx, cy, s.sw
    if kind == "tiktok":
        s.stroke(rrect(x - 28, y - 28, 56, 56, 12), closed=True, w=SW * 0.8)
        s.stroke(densify([(x + 4, y - 16), (x + 4, y + 10)]), w=SW * 0.8, amp=0.3)
        circle(s, x - 5, y + 11, 7, w=SW * 0.7, amp=0.2)
    elif kind == "instagram":
        s.stroke(rrect(x - 28, y - 28, 56, 56, 16), closed=True, w=SW * 0.8)
        circle(s, x, y, 12, w=SW * 0.8, amp=0.3)
        s.dot(x + 16, y - 16, 3.5)
    else:
        s.stroke(seg((x - 20, y - 22), (x + 20, y + 22)), w=SW, amp=0.4)
        s.stroke(seg((x + 20, y - 22), (x - 20, y + 22)), w=SW, amp=0.4)


def ngon(s, cx, cy, r, n=6, start=0.0, lw=None):
    """Regular polygon (T mcp hexagon): corner i at angle TAU/n*i + start (radians)."""
    pts = [(cx + r * math.cos(TAU / n * i + start), cy + r * math.sin(TAU / n * i + start)) for i in range(n)]
    s.stroke(poly(pts), closed=True, w=s.sw if lw is None else lw)
