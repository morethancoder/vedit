"""A pack's `doodle.yaml`: line style and lettering for doodle scenes, merged down the pack's extends chain.

    stroke: "#FAF9F5"     # main line colour        accent: fills, highlights     soft: secondary marks/labels
    warn: "#FF7A59"       # errors, crosses         width: 4.6 (px at 1080p)       wobble: 1.0 (amplitude x)
    lettering: {latin: '"Caveat", cursive', arabic: '"Aref Ruqaa", serif', mono: '"JetBrains Mono", monospace',
                arabic_scale: 0.92}
    shadow: "0 2px 14px rgba(8, 8, 6, 0.6)"   # behind lettered labels
    motion: {pen: power1.inOut, fill: sine.inOut, label: power2.out, out: power1.in}   # GSAP eases (T)

A colour may name a pack colour (`accent` follows a channel accent). Font families must be in pack.yaml `fonts`.
"""

from __future__ import annotations

import yaml

from vedit.doodles.scene import Style
from vedit.report import VeditError

COLORS = ("stroke", "accent", "soft", "warn")
KEYS = {*COLORS, "width", "wobble", "lettering", "shadow", "motion"}
MOTION = {"pen", "fill", "label", "out"}
LETTERING = {"latin", "arabic", "mono", "arabic_scale"}
DEFAULT = {
    "stroke": "#FAF9F5", "accent": "accent", "soft": "accent", "warn": "#FF7A59", "width": 4.6, "wobble": 1.0,
    "lettering": {"latin": "sans-serif", "arabic": "sans-serif", "mono": "monospace", "arabic_scale": 1.0},
    "shadow": "0 2px 14px rgba(8, 8, 6, 0.6)",
    "motion": {"pen": "power1.inOut", "fill": "sine.inOut", "label": "power2.out", "out": "power1.in"},
}  # fmt: skip


def _read(f) -> dict:
    try:
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise VeditError(f"{f}: not valid YAML ({str(e).splitlines()[0]})", next="vedit styles") from e
    if not isinstance(data, dict):
        raise VeditError(
            f"{f}: must be a mapping (stroke, accent, width, lettering, ...)", next="vedit styles"
        )
    return data


def files(pk) -> list:
    """doodle.yaml files of the chain, base first (later ones win)."""
    return [d / "doodle.yaml" for d in reversed(pk.dirs) if (d / "doodle.yaml").is_file()]


def raw(pk) -> dict:
    out = {**DEFAULT, "lettering": dict(DEFAULT["lettering"]), "motion": dict(DEFAULT["motion"])}
    for f in files(pk):
        for k, v in _read(f).items():
            out[k] = {**out.get(k, {}), **v} if k in ("lettering", "motion") and isinstance(v, dict) else v
    return out


def load(pk, accent: str | None = None) -> tuple[Style, dict]:
    """(Style for drawing, template context: lettering stacks, shadow, ink, `m` eases). `accent` is a channel
    accent override."""
    d = raw(pk)
    colors = dict(pk.data.get("colors") or {})
    if accent:
        colors["accent"] = accent

    def col(v):
        return str(colors.get(v, v))

    st = Style(
        ink=col(d["stroke"]),
        accent=col(d["accent"]),
        soft=col(d["soft"]),
        warn=col(d["warn"]),
        width=float(d["width"]),
        wobble=float(d["wobble"]),
        arabic_scale=float(d["lettering"].get("arabic_scale", 1.0)),
    )
    lt = d["lettering"]
    font = {"latin": lt["latin"], "arabic": lt["arabic"], "mono": lt["mono"], "shadow": d["shadow"]}
    return st, {**font, "ink": st.ink, "m": dict(d["motion"])}


def check(pk) -> list[str]:
    """Problems of the pack's doodle.yaml files (unknown keys, wrong kinds)."""
    errs = []
    for f in files(pk):
        where = f"{f.parent.name}/doodle.yaml"
        try:
            data = _read(f)
        except VeditError as e:
            errs.append(e.message)
            continue
        for k, v in data.items():
            if k not in KEYS:
                errs.append(f"{where}: unknown key {k!r} (keys: {', '.join(sorted(KEYS))})")
            elif k in (*COLORS, "shadow") and not isinstance(v, str):
                errs.append(f"{where}: {k} must be a colour (or a pack colour name)")
            elif k in ("width", "wobble") and (
                not isinstance(v, int | float) or isinstance(v, bool) or v <= 0
            ):
                errs.append(f"{where}: {k} must be a number > 0")
            elif k == "motion":
                if not isinstance(v, dict) or not all(isinstance(x, str) and x for x in v.values()):
                    errs.append(f"{where}: motion must map pen/fill/label/out to GSAP ease names")
                    continue
                errs += [
                    f"{where}: motion has no {x!r} (keys: {', '.join(sorted(MOTION))})"
                    for x in v
                    if x not in MOTION
                ]
            elif k == "lettering":
                if not isinstance(v, dict):
                    errs.append(f"{where}: lettering must map latin/arabic/mono to CSS font stacks")
                    continue
                errs += [
                    f"{where}: lettering has no {x!r} (keys: {', '.join(sorted(LETTERING))})"
                    for x in v
                    if x not in LETTERING
                ]
    have = {f.get("family") for f in pk.data.get("fonts") or [] if isinstance(f, dict)}
    try:
        lt = raw(pk).get("lettering") or {}
    except VeditError:
        lt = {}
    own = (pk.dirs[0] / "doodle.yaml").is_file()  # an inherited doodle.yaml may name fonts this pack dropped
    for k in ("latin", "arabic", "mono") if own else ():
        fam = str(lt.get(k, "") if isinstance(lt, dict) else "").split(",")[0].strip().strip("'\"")
        if fam and fam not in GENERIC and fam not in have:
            errs.append(f"{pk.name}: doodle lettering.{k} font {fam!r} is not in pack.yaml fonts")
    return errs


GENERIC = {"serif", "sans-serif", "monospace", "cursive", "fantasy", "system-ui"}
