"""Scene specs: validation, the short `elements:` form, and drawing a spec into a Scene (docs/formats.md).

Full form (the library, `vedit/doodles/scenes/*.yaml`): `beats:` maps each beat, in drawing order, to its
steps. A step is a pen pass (`pen` seconds or `next` = joins the next pass's stroke, `shapes`, optional `after`, `float`, `name`, `into`, `spin`) or a
hand-lettered `text` (`at`, `after`, `size`, `color`, `mono`, `anchor`, `weight`). Times are seconds after the
beat's spoken words.

Short form (inline in cues.yaml): `elements:` is a list of {beat, one shape, optional id, at, label}; arrows
join elements by id (`arrow: {from: bot, to: phone}`), and `layout: row|column` spreads the elements that give
no `at` (a row runs right to left for an RTL language). It compiles to the full form.
"""

from __future__ import annotations

import difflib
import math
import re

from vedit.doodles import shapes
from vedit.doodles.scene import Scene, Style

PASS_KEYS = {"pen", "shapes", "after", "float", "name", "into", "spin"}
TEXT_KEYS = {"text", "at", "after", "size", "weight", "color", "mono", "anchor", "mode", "d"}
TOP_KEYS = {"name", "lang", "seed", "about", "beats", "elements", "layout"}
EL_KEYS = {"beat", "id", "label", "at", "pen", "after", "float", "text", "size", "color"}
ANCHORS = {"middle", "start", "end"}
TOP_LEFT = {"rect", "window", "bubble", "barchart"}
RTL = re.compile(r"^(ar|fa|ur|he)\b")

# sizes an element gets when the short form gives none (px at 1920x1080), and its half extents
DEFAULTS = {
    "bot": {"w": 220, "h": 190}, "laptop": {"w": 340}, "phone": {"w": 200, "h": 360},
    "play_phone": {"w": 150, "h": 260}, "server": {"w": 280}, "rack": {}, "person": {"size": 110},
    "people": {"size": 90}, "megaphone": {"size": 150}, "key": {}, "clock": {"R": 90}, "gear": {"R": 70},
    "telegram": {"R": 80}, "envelope": {"w": 90}, "coin": {"R": 60}, "shop": {"w": 240},
    "stopwatch": {"R": 75}, "diamond": {"w": 280, "h": 170}, "plug": {"size": 150}, "gift": {"w": 120},
    "hardhat": {"w": 150}, "gauge": {"R": 120}, "tag": {"w": 220, "h": 64}, "social": {}, "spark": {"R": 60},
    "check": {"k": 110}, "cross": {"k": 40}, "qmark": {"r": 46}, "play": {"k": 90}, "circle": {"r": 70},
    "oval": {"rx": 120, "ry": 80}, "ngon": {"r": 60}, "window": {"w": 320, "h": 220},
    "bubble": {"w": 300, "h": 110}, "barchart": {"w": 240, "h": 170}, "rect": {"w": 300, "h": 150},
}  # fmt: skip


def _half(kind: str, p: dict) -> tuple[float, float]:
    g = {**DEFAULTS.get(kind, {}), **p}
    w, h = g.get("w"), g.get("h")
    if kind == "laptop":
        return w * 0.6, w * 0.31 + 20
    if kind == "server":
        n, uh = g.get("units", 3), g.get("unit_h", 84)
        return w / 2, (n * uh + (n - 1) * g.get("gap", 14)) / 2
    if kind == "rack":
        return g.get("w", 250) / 2, g.get("h", 340) / 2
    if kind in ("person", "people", "megaphone", "plug"):
        k = {"person": (0.7, 1.0), "people": (1.45, 1.0), "megaphone": (0.8, 0.62), "plug": (0.9, 0.4)}[kind]
        return g["size"] * k[0], g["size"] * k[1]
    if kind == "key":
        return 110 * g.get("size", 1.0), 40 * g.get("size", 1.0)
    for r in ("R", "r", "rx", "k"):
        if r in g:
            return float(g[r]), float(g.get("ry", g[r]) if r == "rx" else g[r])
    if w is not None:
        return w / 2, (h if h is not None else w * 0.7) / 2
    return 60.0, 60.0


def _num(v) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool)


COLOR_OK = re.compile(
    r"^(?:#(?:[0-9A-Fa-f]{3,4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})|[A-Za-z][A-Za-z0-9_-]{0,31})$"
)
MODES = {"w", "r", "f"}


def _color_ok(v) -> bool:
    """A token (ink, accent, soft, warn), a pack colour name or CSS colour name, or #hex: never markup."""
    return isinstance(v, str) and bool(COLOR_OK.match(v))


def _pt(v) -> bool:
    return isinstance(v, list) and len(v) == 2 and all(_num(x) for x in v)


def _close(k, have) -> str:
    c = difflib.get_close_matches(str(k), sorted(have), n=1)
    return f"; did you mean {c[0]!r}?" if c else ""


def check_shape(sh, where: str) -> list[str]:
    if not isinstance(sh, dict) or len(sh) != 1:
        return [
            f"{where}: a shape is one `kind: {{params}}` mapping, like `bot: {{at: [500, 570], w: 240, h: 210}}`"
        ]
    kind, p = next(iter(sh.items()))
    if kind not in shapes.KINDS:
        return [
            f"{where}: unknown shape {kind!r}{_close(kind, shapes.KINDS)} (shapes: {', '.join(sorted(shapes.KINDS))})"
        ]
    p = p or {}
    if not isinstance(p, dict):
        return [f"{where}: {kind} params must be a mapping"]
    required, accepted, at_ok = shapes.params(kind)
    errs = [
        f"{where}: {kind} has no {k!r}{_close(k, accepted)} (takes: {', '.join(sorted(accepted))})"
        for k in p
        if k not in accepted
    ]
    need = required[2:] if at_ok and "at" in p else required
    errs += [
        f"{where}: {kind} needs {k!r}" + (" (or `at: [x, y]`)" if at_ok and k in required[:2] else "")
        for k in need
        if k not in p
    ]
    at = p.get("at")
    if at is not None and not (_pt(at) or (isinstance(at, list) and at and all(_pt(a) for a in at))):
        errs.append(f"{where}: {kind} `at` must be [x, y] or a list of [x, y]")
    for k, v in p.items():
        if k == "color" and not _color_ok(v):
            errs.append(
                f"{where}: {kind} `color` must be ink, accent, soft, warn, a pack colour name or #hex"
            )
        if k == "fill" and isinstance(v, dict) and "color" in v and not _color_ok(v["color"]):
            errs.append(
                f"{where}: {kind} `fill.color` must be ink, accent, soft, warn, a pack colour name or #hex"
            )
        if k in ("pts",) and not (isinstance(v, list) and len(v) >= 2 and all(_pt(a) for a in v)):
            errs.append(f"{where}: {kind} `{k}` must be a list of at least two [x, y]")
        if k in ("a", "b", "via") and not _pt(v):
            errs.append(f"{where}: {kind} `{k}` must be [x, y]")
    return errs


def _check_full(spec: dict, w: str) -> list[str]:
    beats = spec.get("beats")
    if not isinstance(beats, dict) or not beats:
        return [f"{w}: needs `beats:` (beat -> steps) or `elements:`"]
    errs, names = [], set()
    for b, steps in beats.items():
        if not isinstance(b, str):
            errs.append(f"{w}: beat {b!r} must be text (quote no/on/yes)")
        if not isinstance(steps, list) or not steps:
            errs.append(f"{w}.beats.{b}: must be a list of steps (pen passes and texts)")
            continue
        for i, st in enumerate(steps):
            sw = f"{w}.beats.{b}[{i}]"
            if not isinstance(st, dict):
                errs.append(f"{sw}: a step is a mapping with `pen` + `shapes`, or `text` + `at`")
                continue
            keys = TEXT_KEYS if "text" in st else PASS_KEYS
            errs += [f"{sw}: unknown key {k!r}{_close(k, keys)}" for k in st if k not in keys]
            if not _num(st.get("after", 0)):
                errs.append(f"{sw}: `after` must be seconds")
            if "text" in st:
                if not _pt(st.get("at")):
                    errs.append(f"{sw}: text needs `at: [x, y]`")
                if st.get("anchor", "middle") not in ANCHORS:
                    errs.append(f"{sw}: anchor must be middle, start or end")
                for k in ("size", "weight", "d"):
                    if k in st and (not _num(st[k]) or st[k] <= 0):
                        errs.append(f"{sw}: `{k}` must be a number > 0")
                if "mode" in st and st["mode"] not in MODES:
                    errs.append(f"{sw}: mode must be w, r or f")
                if "color" in st and not _color_ok(st["color"]):
                    errs.append(f"{sw}: `color` must be ink, accent, soft, warn, a pack colour name or #hex")
                continue
            if st.get("pen") != "next" and (not _num(st.get("pen")) or st["pen"] <= 0):
                errs.append(
                    f"{sw}: a pen pass needs `pen: <seconds>` (or `next`) and `shapes:`, or write `text:`"
                )
            if not isinstance(st.get("shapes"), list):
                errs.append(f"{sw}: `shapes` must be a list")
            else:
                for j, sh in enumerate(st["shapes"]):
                    errs += check_shape(sh, f"{sw}.shapes[{j}]")
            if st.get("into") is not None and st["into"] not in names:
                errs.append(f"{sw}: `into: {st['into']}` names no earlier pass (`name:` it first)")
            if st.get("name"):
                names.add(st["name"])
            sp = st.get("spin")
            if sp is not None and not (
                isinstance(sp, dict) and _pt(sp.get("about")) and _num(sp.get("rate"))
            ):
                errs.append(f"{sw}: spin is {{about: [x, y], rate: <deg/s>, after: <s>, of: <pass name>}}")
            elif sp is not None and sp.get("of") is not None and sp["of"] not in names:
                errs.append(f"{sw}: spin `of: {sp['of']}` names no earlier pass")
    return errs


def _check_short(spec: dict, w: str) -> list[str]:
    els = spec.get("elements")
    if not isinstance(els, list) or not els:
        return [f"{w}: `elements:` must be a non-empty list"]
    errs, ids, arrows = [], set(), set()
    if spec.get("layout", "row") not in ("row", "column"):
        errs.append(f"{w}: layout must be row or column")
    for i, el in enumerate(els):
        ew = f"{w}.elements[{i}]"
        if not isinstance(el, dict) or not isinstance(el.get("beat"), str):
            errs.append(f"{ew}: needs `beat: <name>` (the cue's beats map it to spoken words)")
            continue
        kinds = [k for k in el if k not in EL_KEYS]
        if "size" in el and (not _num(el["size"]) or el["size"] <= 0):
            errs.append(f"{ew}: `size` must be a number > 0")
        if "color" in el and not _color_ok(el["color"]):
            errs.append(f"{ew}: `color` must be ink, accent, soft, warn, a pack colour name or #hex")
        if "text" in el:
            if kinds:
                errs.append(f"{ew}: a text element takes no shape ({', '.join(kinds)})")
            if not _pt(el.get("at")):
                errs.append(f"{ew}: text needs `at: [x, y]`")
            continue
        if len(kinds) != 1:
            errs.append(
                f"{ew}: one shape per element (got {', '.join(map(str, kinds)) or 'none'}); keys: {', '.join(sorted(EL_KEYS))}"
            )
            continue
        kind = kinds[0]
        if kind == "arrow" and isinstance(el[kind], dict):
            a = el[kind]
            for end in ("from", "to"):
                v = a.get(end)
                if isinstance(v, str) and v in arrows:
                    errs.append(f"{ew}: arrow `{end}` {v!r} is an arrow; name a shape's id or give [x, y]")
                elif not (_pt(v) or (isinstance(v, str) and v in ids)):
                    errs.append(f"{ew}: arrow `{end}` must be [x, y] or the id of an earlier element")
            rest = {k: v for k, v in a.items() if k not in ("from", "to")}
            errs += [e for e in check_shape({"arrow": {**rest, "a": [0, 0], "b": [1, 1]}}, ew)]
        else:
            p = dict(el[kind] or {})
            if el.get("at") is not None:
                p["at"] = el["at"]
            errs += check_shape({kind: {**DEFAULTS.get(kind, {}), "at": [0, 0], **p}}, ew)
        if el.get("id"):
            (arrows if kind == "arrow" else ids).add(el["id"])
    return errs


def check(spec, where: str = "scene") -> list[str]:
    """Every problem of a spec (empty = valid)."""
    if not isinstance(spec, dict):
        return [f"{where}: a scene spec is a mapping with `beats:` or `elements:`"]
    errs = [f"{where}: unknown key {k!r}{_close(k, TOP_KEYS)}" for k in spec if k not in TOP_KEYS]
    if "elements" in spec:
        return errs + _check_short(spec, where)
    return errs + _check_full(spec, where)


def beat_names(spec: dict) -> list[str]:
    if "elements" in spec:
        return list(dict.fromkeys(el["beat"] for el in spec["elements"]))
    return list(spec["beats"])


def _edge(c, half, toward) -> tuple[float, float]:
    """Point just outside an element's box on the way to `toward`."""
    dx, dy = toward[0] - c[0], toward[1] - c[1]
    d = math.hypot(dx, dy) or 1.0
    ux, uy = dx / d, dy / d
    t = min(half[0] / abs(ux) if ux else 1e9, half[1] / abs(uy) if uy else 1e9) + 24
    return (round(c[0] + ux * t, 1), round(c[1] + uy * t, 1))


def expand(spec: dict, lang: str = "ar") -> dict:
    """The short `elements:` form as the full `beats:` form (a full spec comes back unchanged)."""
    if "elements" not in spec:
        return spec
    els = spec["elements"]
    column = spec.get("layout") == "column"
    free = [i for i, el in enumerate(els) if "text" not in el and "arrow" not in el and el.get("at") is None]
    n = len(free)
    spots = [
        (960, round(1080 * (k + 1) / (n + 1))) if column else (round(1920 * (k + 1) / (n + 1)), 470)
        for k in range(n)
    ]
    if not column and RTL.match(spec.get("lang") or lang):
        spots.reverse()
    where, boxes = dict(zip(free, spots, strict=True)), {}
    beats: dict[str, list] = {}
    for i, el in enumerate(els):
        steps = beats.setdefault(el["beat"], [])
        after = float(el.get("after", 0))
        if "text" in el:
            steps.append(
                {
                    "text": el["text"],
                    "at": el["at"],
                    "after": after,
                    "size": el.get("size", 58),
                    "color": el.get("color", "ink"),
                }
            )
            continue
        kind = next(k for k in el if k not in EL_KEYS)
        if kind == "arrow" and isinstance(el[kind], dict):
            a = dict(el[kind])
            fa, ta = a.pop("from"), a.pop("to")
            pa = boxes[fa][0] if isinstance(fa, str) else tuple(fa)
            pb = boxes[ta][0] if isinstance(ta, str) else tuple(ta)
            p0 = _edge(pa, boxes[fa][1], pb) if isinstance(fa, str) else pa
            p1 = _edge(pb, boxes[ta][1], pa) if isinstance(ta, str) else pb
            steps.append(
                {
                    "pen": el.get("pen", 0.6),
                    "after": after,
                    "shapes": [{"arrow": {"size": 22, **a, "a": list(p0), "b": list(p1)}}],
                }
            )
            if el.get("label"):
                mid = [round((p0[0] + p1[0]) / 2), round((p0[1] + p1[1]) / 2) - 50]
                steps.append(
                    {
                        "text": el["label"],
                        "at": mid,
                        "after": after + 0.3,
                        "size": el.get("size", 50),
                        "color": el.get("color", "soft"),
                    }
                )
            continue
        p = {**DEFAULTS.get(kind, {}), **(el[kind] or {})}
        c = tuple(el["at"]) if el.get("at") is not None else where[i]
        half = _half(kind, p)
        at = [c[0] - p["w"] / 2, c[1] - p["h"] / 2] if kind in TOP_LEFT else list(c)
        steps.append(
            {
                "pen": el.get("pen", 1.0),
                "after": after,
                "float": el.get("float", 4),
                "shapes": [{kind: {**p, "at": at}}],
            }
        )
        if el.get("id"):
            boxes[el["id"]] = (c, half)
        if el.get("label"):
            steps.append(
                {
                    "text": el["label"],
                    "at": [c[0], round(c[1] + half[1] + 60)],
                    "after": after + 0.6,
                    "size": el.get("size", 58),
                    "color": el.get("color", "ink"),
                }
            )
    return {k: v for k, v in spec.items() if k not in ("elements", "layout")} | {"beats": beats}


def resolve_beats(order: list[str], dur: float, beats: dict[str, float]) -> dict[str, float]:
    """Local seconds per beat (T `_resolve_beats`): a missing beat is spaced evenly; all clamp into the scene
    and the earliest starts by 0.12 s (drawing starts with the blur, never on an empty blurred frame)."""
    n = len(order)
    first, last = 0.12, max(0.6, dur - 3.0)
    out = {}
    for i, b in enumerate(order):
        even = first + (last - first) * (i / (n - 1) if n > 1 else 0)
        v = beats.get(b) if beats else None
        out[b] = float(even if v is None else v)
    lo, hi = 0.05, max(0.3, dur - 1.6)
    out = {b: min(max(v, lo), hi) for b, v in out.items()}
    early = min(out, key=out.get)
    out[early] = min(out[early], 0.12)
    return out


def draw(spec: dict, seed: int, dur: float, beats: dict[str, float], style: Style | None = None) -> Scene:
    """Draw a full-form spec: `beats` maps beat -> local seconds (missing ones spaced evenly)."""
    s = Scene(seed, float(dur), style)
    B = resolve_beats(list(spec["beats"]), float(dur), beats)
    named: dict[str, int] = {}
    for b, steps in spec["beats"].items():
        t = B[b]
        for st in steps:
            at = t + float(st.get("after", 0))
            if "text" in st:
                x, y = st["at"]
                kw = {k: st[k] for k in ("size", "weight", "color", "mono", "anchor", "mode", "d") if k in st}
                s.label(st["text"], x, y, at, **kw)
                continue
            if st.get("into"):
                s.use(named[st["into"]])
            else:
                k = s.group(float_px=st.get("float", 0.0))
                if st.get("name"):
                    named[st["name"]] = k
            for sh in st["shapes"]:
                kind, p = next(iter(sh.items()))
                shapes.call(s, kind, p or {})
            if st["pen"] != "next":  # `next`: these shapes join the next pass's pen stroke
                s.draw(at, float(st["pen"]))
            if st.get("spin"):
                sp = st["spin"]
                k = named[sp["of"]] if sp.get("of") else s.cur["k"]
                s.spin(k, sp["about"][0], sp["about"][1], sp["rate"], t + float(sp.get("after", 0)))
    return s
