"""Pack checker: every problem of a style pack at once, as plain lines (`pack.check(pk)`).

Checked: each pack.yaml of the extends-chain (valid YAML, known top-level keys with a closest-key hint, `name`
matching the folder), the merged tokens (colours, fonts and their files, themes, motion, advances, sfx map and
its files, logo names), every type template and partial (slot header, slot kinds, paired sections), and the
doodle.yaml files (keys, colours, lettering fonts present in `fonts`; vedit/doodles/style.py).
`vedit build` and `vedit styles` run it; a pack with problems is not used.
"""

from __future__ import annotations

import difflib
import json

from vedit.graphics import pack as packs
from vedit.report import VeditError

THEMES = ("dark", "light")  # placement picks one per cue from the brightness behind it
THEME_TOKENS = ("text", "sub", "kicker", "shadow")  # read by base partials; other tokens are pack-defined
MOTION_KEYS = {
    "ease_in", "ease_out", "ease_draw", "ease_pop",
    "in", "out", "out_lead", "scene_out", "scene_lead", "stagger", "rise",
}  # fmt: skip


def _rel(pk, f) -> str:
    for d in pk.dirs:
        try:
            return f"{d.name}/{f.relative_to(d)}"
        except ValueError:
            continue
    return str(f)


def _num(v) -> bool:
    return isinstance(v, int | float) and not isinstance(v, bool)


def _yaml_files(pk) -> list[str]:
    errs = []
    for d in pk.dirs:
        try:
            data = packs.read_yaml(d)
        except VeditError as e:
            errs.append(e.message)
            continue
        for k in data:
            if k not in packs.KEYS:
                close = difflib.get_close_matches(str(k), sorted(packs.KEYS), n=1)
                errs.append(
                    f"{d.name}/pack.yaml: unknown key {k!r}"
                    + (f"; did you mean {close[0]!r}?" if close else "")
                )
        if data.get("name") not in (None, d.name):
            errs.append(f"{d.name}/pack.yaml: name {data['name']!r} differs from its folder {d.name!r}")
    return errs


def _tokens(pk) -> list[str]:
    d, errs = pk.data, []
    w = f"{pk.name}: pack.yaml"
    for key in ("colors", "font"):
        v = d.get(key) or {}
        if not isinstance(v, dict) or not all(isinstance(x, str) for x in v.values()):
            errs.append(f"{w}: {key} must map names to strings")
    fonts = d.get("fonts") or []
    if not isinstance(fonts, list):
        errs.append(f"{w}: fonts must be a list of {{family, file, weight}}")
        fonts = []
    for i, f in enumerate(fonts):
        if not isinstance(f, dict) or not f.get("family") or not f.get("file"):
            errs.append(f"{w}: fonts[{i}] needs family and file")
        elif pk.file(str(f["file"])) is None:
            errs.append(f"{w}: font file {f['file']!r} is not in the pack (fonts[{i}])")
    themes = d.get("themes") or {}
    for t in THEMES:
        th = themes.get(t) if isinstance(themes, dict) else None
        if not isinstance(th, dict):
            errs.append(f"{w}: themes.{t} is missing")
            continue
        miss = [k for k in THEME_TOKENS if k not in th]
        if miss:
            errs.append(f"{w}: themes.{t} lacks {', '.join(miss)}")
    if d.get("busy_shadow") is not None and not isinstance(d["busy_shadow"], str):
        errs.append(f"{w}: busy_shadow must be a CSS text-shadow string")
    errs += _motion(w, d.get("motion"))
    adv = d.get("advances")
    if adv:
        f = pk.file(str(adv))
        if f is None:
            errs.append(f"{w}: advances file {adv!r} is not in the pack")
        else:
            try:
                ok = isinstance(json.loads(f.read_text(encoding="utf-8")), dict)
            except ValueError:
                ok = False
            if not ok:
                errs.append(f"{w}: advances file {adv!r} is not a JSON object (char -> em)")
    errs += _sfx(pk, w)
    spin = (d.get("logo_motion") or {}).get("spin") or []
    logos = pk.logos()
    errs += [f"{w}: logo_motion.spin names {n!r}, which is not in logos/" for n in spin if n not in logos]
    return errs


def _motion(w: str, m) -> list[str]:
    if not isinstance(m, dict):
        return [f"{w}: motion must be a mapping (ease_in, out, stagger, ...)"]
    errs = [f"{w}: motion lacks {k}" for k in sorted(MOTION_KEYS - set(m))]
    for k, v in m.items():
        if str(k).startswith("ease"):
            if not isinstance(v, str) or not v:
                errs.append(f"{w}: motion.{k} must be a GSAP ease name like power3.out")
        elif not _num(v) or v < 0:
            errs.append(f"{w}: motion.{k} must be a number >= 0 (seconds, or px for rise)")
    return errs


def _sfx(pk, w: str) -> list[str]:
    errs = []
    table, lens = pk.data.get("sfx") or {}, pk.data.get("sfx_files") or {}
    if not isinstance(table, dict) or not isinstance(lens, dict):
        return [f"{w}: sfx must map kind -> [sound, gain] and sfx_files sound -> seconds"]
    for kind, v in table.items():
        if not (isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and _num(v[1]) and v[1] > 0):
            errs.append(f"{w}: sfx.{kind} must be [sound, gain] (gain > 0)")
            continue
        if pk.file(f"sfx/{v[0]}.mp3") is None:
            errs.append(f"{w}: sfx.{kind} sound sfx/{v[0]}.mp3 is not in the pack")
        if not _num(lens.get(v[0])):
            errs.append(f"{w}: sfx_files has no length for {v[0]!r} (seconds, from ffprobe)")
    return errs


def _templates(pk) -> list[str]:
    errs, files = [], []
    for d in pk.dirs:
        for sub in ("types", "partials"):
            if (d / sub).is_dir():
                files += sorted((d / sub).glob("*.html"))
    for f in files:
        try:
            t = packs._parse_template(f.stem, f)
        except VeditError as e:
            errs.append(e.message)
            continue
        except UnicodeDecodeError:
            errs.append(f"{_rel(pk, f)}: not UTF-8 text")
            continue
        for e in packs.syntax(t.style + "\n" + t.body + "\n" + t.script):
            errs.append(f"{_rel(pk, f)}: {e}")
    return errs


def check(pk) -> list[str]:
    from vedit.doodles import style as doodle_style

    return _yaml_files(pk) + _tokens(pk) + _templates(pk) + doodle_style.check(pk)
