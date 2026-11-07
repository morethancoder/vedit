"""The scene library: `vedit/doodles/scenes/<name>.yaml` (full-form specs, docs/formats.md), and turning a cue's
`scene:` (a library name or an inline spec) into a drawn scene for the pack template.
"""

from __future__ import annotations

import difflib
import json
import zlib
from functools import cache
from pathlib import Path

import yaml

from vedit.doodles import spec as specs
from vedit.doodles import style as styles
from vedit.report import VeditError

DIR = Path(__file__).resolve().parent / "scenes"
CODE = sorted(Path(__file__).resolve().parent.glob("*.py"))  # the drawing engine, part of every page key


def names() -> list[str]:
    return sorted(f.stem for f in DIR.glob("*.yaml"))


def file_of(name: str) -> Path:
    return DIR / f"{name}.yaml"


@cache
def _load(name: str) -> dict:
    return yaml.safe_load(file_of(name).read_text(encoding="utf-8"))


def _missing(name: str) -> str:
    close = difflib.get_close_matches(name, names(), n=1)
    hint = f"; did you mean {close[0]!r}?" if close else ""
    return f"no library scene {name!r}{hint} (scenes: {', '.join(names())})"


def scene(name: str) -> dict:
    if name not in names():
        raise VeditError(_missing(name), next="vedit guide cue-doodle")
    return _load(name)


def resolve(value, where: str = "scene", lang: str = "ar") -> tuple[dict, int]:
    """(full-form spec, seed) of a cue's `scene:`: a library name (seed = crc32 of the name, as T), or an
    inline spec (checked; seed = its `seed:` or a hash of the spec)."""
    if isinstance(value, str):
        sp = scene(value)
        return sp, int(sp.get("seed", zlib.crc32(value.encode())))
    errs = specs.check(value, where)
    if errs:
        raise VeditError("\n".join(errs), next="vedit guide cue-doodle")
    seed = value.get("seed")
    if not isinstance(seed, int):
        src = json.dumps(value, sort_keys=True, ensure_ascii=False) if seed is None else str(seed)
        seed = zlib.crc32(src.encode())
    return specs.expand(value, lang), seed


def check_cue(fields: dict, where: str) -> list[str]:
    """Problems of a doodle cue's scene and beat names (each beat key must be a beat of the scene)."""
    value = fields.get("scene")
    if isinstance(value, str):
        if value not in names():
            return [f"{where}: {_missing(value)}"]
        order = specs.beat_names(scene(value))
    elif isinstance(value, dict):
        errs = specs.check(value, f"{where} scene")
        if errs:
            return errs
        order = specs.beat_names(value)
    else:
        return []  # the slot check reports the wrong kind
    beats = fields.get("beats") if isinstance(fields.get("beats"), dict) else {}
    return [
        f"{where}: beat {b!r} is not in the scene (beats: {', '.join(order)})"
        for b in beats
        if isinstance(b, str) and b not in order
    ]


def drawn(
    value, dur: float, beats: dict[str, float], pk, accent: str | None = None, lang: str = "ar"
) -> dict:
    """Template context `doodle.*` for a scene drawn over `dur` seconds, beats at local seconds."""
    sp, seed = resolve(value, lang=lang)
    st, look = styles.load(pk, accent)
    s = specs.draw(sp, seed, dur, beats, st)

    def js(v):
        return json.dumps(v, separators=(",", ":"))

    return {
        "svg": s.svg(),
        "labels": "".join(s.labels_html),
        "draw": js(s.draws),
        "fill": js(s.fades),
        "lab": js(s.labs),
        "float": js(s.floats()),
        "spin": js(s.spins),
        "fade_at": round(max(0.0, dur - 0.6), 3),
        "font": {k: v for k, v in look.items() if k != "m"},
        "m": look["m"],
    }


def key_parts(value, pk) -> list:
    """What a doodle page is built from beyond the cue: the scene file, doodle.yaml files, the engine."""
    parts: list = [*CODE, *styles.files(pk)]
    if isinstance(value, str) and file_of(value).is_file():
        parts.append(file_of(value))
    return parts
