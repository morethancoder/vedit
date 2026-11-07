"""Style packs: pack.yaml tokens, per-type templates with declared slots, and the template engine.

A pack is a folder `styles/<name>/` with `pack.yaml` and `types/<type>.html`. A type missing from a pack falls
back to its `extends:` pack, then to `base`. Each template starts with a header comment that declares the cue
fields it accepts (its slots); cues are validated against it, so an unknown field is an error, not ignored.

    <!-- vedit
    slots:
      title: {required: true}
      logo: {kind: logo}
    -->
    <style> ... </style>
    <div class="wrap {{side}}"> ... {{title}} ... </div>
    <script> ... tl.fromTo(...) ... </script>

Template mechanism (decided in phase 04, recorded in plans/principles.md): a mustache subset, no logic in
templates beyond it. `{{x}}` escaped, `{{&x}}` raw, `{{#x}}..{{/x}}` (list: repeat per item; dict: push it;
truthy: once), `{{^x}}..{{/x}}` (falsy: once), dotted names (`{{th.text}}`), `{{.}}` the current item.
The context names every template gets are listed in vedit/graphics/pages.py; `check()` (packcheck.py) finds
every problem of a pack at once.

Packs resolve over `pack_roots(channel)`: the channel's `<config_dir>/channels/<handle>/styles/`, then the
global `<config_dir>/styles/`, then the built-in `vedit/styles/`; the nearest wins. `drafts/` under the global
styles holds packs being authored and is never a pack name.
"""

from __future__ import annotations

import difflib
import html
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from vedit.channel import config_dir
from vedit.report import VeditError

BUILTIN = Path(__file__).resolve().parent.parent / "styles"
BASE = "base"
DRAFTS = "drafts"  # under the global styles: packs being authored, not a pack name
# pack.yaml top-level keys (docs/formats.md "Style pack"); anything else is a typo the checker reports
KEYS = {
    "name", "extends", "summary", "keywords", "lang",
    "colors", "fonts", "font", "themes", "busy_shadow", "motion",
    "advances", "big", "logo_motion", "focus", "sfx", "sfx_files",
}  # fmt: skip


def user_root() -> Path:
    """Global user packs: `<config_dir>/styles/` (VEDIT_CONFIG_DIR honoured, read at call time)."""
    return config_dir() / "styles"


def channel_root(handle: str) -> Path:
    """A channel's own packs: `<config_dir>/channels/<handle>/styles/`."""
    return config_dir() / "channels" / handle / "styles"


def pack_roots(channel: str | None = None) -> list[Path]:
    """Where pack names resolve, nearest first: the channel's, global, built-in."""
    return ([channel_root(channel)] if channel else []) + [user_root(), BUILTIN]


def scope_of(root: Path) -> str:
    """`built-in`, `global` or `channel:<handle>` for a pack root."""
    if root == BUILTIN:
        return "built-in"
    return "global" if root == user_root() else f"channel:{root.parent.name}"


def where(roots: list[Path]) -> str:
    return "; ".join(f"{scope_of(r)} {r}" for r in roots)


# slot kinds: text (default), bool, number, list (of text), words (a spoken phrase -> a time),
# beats (element -> spoken phrase), logo (a mark the pack offers), file (a path under the project),
# box ([x, y, w, h] in 1920x1080 px), scene (a doodle library scene name or an inline spec mapping, checked by
# vedit/doodles)
KINDS = {"text", "bool", "number", "list", "words", "beats", "logo", "file", "box", "scene"}
# cue keys that are never slots: anchoring and identity, read by the engine itself
CUE_KEYS = {"type", "id", "at", "near", "until", "for", "style", "pick", "window", "until_near"}

_HEADER = re.compile(r"\A\s*<!--\s*vedit\b(.*?)-->", re.DOTALL)


@dataclass
class Slot:
    name: str
    kind: str = "text"
    required: bool = False
    help: str = ""


@dataclass
class TypeTemplate:
    name: str
    pack: str
    path: Path
    slots: dict[str, Slot]
    style: str
    body: str
    script: str
    meta: dict = field(default_factory=dict)


@dataclass
class Pack:
    name: str
    dirs: list[Path]  # this pack first, then what it extends, base last
    data: dict  # merged pack.yaml (this pack wins)

    def file(self, rel: str) -> Path | None:
        for d in self.dirs:
            if (d / rel).exists():
                return d / rel
        return None

    def logos(self) -> dict[str, Path]:
        out: dict[str, Path] = {}
        for d in reversed(self.dirs):
            for f in sorted((d / "logos").glob("*.svg")) if (d / "logos").is_dir() else []:
                out[f.stem] = f
        return out

    def partials(self) -> dict[str, Path]:
        """`partials/<name>.html`: shared CSS/JS fragments the type templates pull in as `{{&part.<name>}}`."""
        out: dict[str, Path] = {}
        for d in reversed(self.dirs):
            for f in sorted((d / "partials").glob("*.html")) if (d / "partials").is_dir() else []:
                out[f.stem] = f
        return out

    def template(self, type_: str) -> TypeTemplate:
        f = self.file(f"types/{type_}.html")
        if f is None:
            raise VeditError(
                f"style {self.name!r} has no template for cue type {type_!r}",
                next="vedit guide cues  (types in v1)",
            )
        return _parse_template(type_, f)

    def types(self) -> list[str]:
        return sorted(self.type_sources())

    def type_sources(self) -> dict[str, str]:
        """type -> the pack (folder name) whose template is used: this pack's own, else the nearest it extends."""
        out: dict[str, str] = {}
        for d in reversed(self.dirs):
            for f in (d / "types").glob("*.html") if (d / "types").is_dir() else []:
                out[f.stem] = d.name
        return dict(sorted(out.items()))

    def advances(self) -> dict[str, float]:
        rel = self.data.get("advances")
        f = self.file(rel) if rel else None
        return json.loads(f.read_text()) if f else {}


def _parse_template(name: str, path: Path) -> TypeTemplate:
    text = path.read_text(encoding="utf-8")
    m = _HEADER.match(text)
    try:
        meta = (yaml.safe_load(m.group(1)) or {}) if m else {}
    except yaml.YAMLError as e:
        raise VeditError(f"{path}: slot header is not valid YAML ({str(e).splitlines()[0]})") from e
    if not isinstance(meta, dict) or not isinstance(meta.get("slots") or {}, dict):
        raise VeditError(
            f"{path}: slot header must be a mapping with `slots:` name -> {{kind, required, help}}"
        )
    rest = text[m.end() :] if m else text
    slots = {}
    for k, v in (meta.get("slots") or {}).items():
        v = v or {}
        if not isinstance(v, dict):
            raise VeditError(f"{path}: slot {k!r} must be a mapping like {{kind: text, required: true}}")
        kind = v.get("kind", "text")
        if kind not in KINDS:
            raise VeditError(
                f"{path}: slot {k!r} has unknown kind {kind!r} (kinds: {', '.join(sorted(KINDS))})"
            )
        slots[k] = Slot(k, kind, bool(v.get("required")), v.get("help", ""))
    style = "\n".join(re.findall(r"<style>(.*?)</style>", rest, re.DOTALL))
    script = "\n".join(re.findall(r"<script>(.*?)</script>", rest, re.DOTALL))
    body = re.sub(r"<(style|script)>.*?</\1>", "", rest, flags=re.DOTALL).strip("\n")
    return TypeTemplate(name, path.parent.parent.name, path, slots, style, body, script, meta)


def _pack_dir(name: str, roots: list[Path]) -> Path:
    for r in roots:
        if name != DRAFTS and (r / name / "pack.yaml").is_file():
            return r / name
    have = sorted({n for n, _, _ in available(roots)})
    close = difflib.get_close_matches(name, have, n=1)
    raise VeditError(
        f"style {name!r} not found; searched {where(roots)} (have: {', '.join(have) or 'none'})"
        + (f"; did you mean {close[0]!r}?" if close else ""),
        next="vedit guide styles",
    )


def _merge(base: dict, over: dict) -> dict:
    out = dict(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def read_yaml(d: Path) -> dict:
    """A pack folder's own pack.yaml as a dict (an error names the file)."""
    f = d / "pack.yaml"
    try:
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise VeditError(f"{f}: not valid YAML ({str(e).splitlines()[0]})", next="vedit styles") from e
    if not isinstance(data, dict):
        raise VeditError(f"{f}: must be a mapping of keys (name, colors, fonts, ...)", next="vedit styles")
    return data


def available(roots: list[Path] | None = None) -> list[tuple[str, Path, Path]]:
    """(name, folder, root) of every pack folder under `roots`, nearest root first (a name may repeat)."""
    out = []
    for r in roots if roots is not None else pack_roots():
        if r.is_dir():
            out += [
                (f.parent.name, f.parent, r) for f in sorted(r.glob("*/pack.yaml")) if f.parent.name != DRAFTS
            ]
    return out


def load(name: str, roots: list[Path] | None = None) -> Pack:
    """Pack `name` resolved over `roots` (default: global, then built-in; pass `pack_roots(channel)` for a channel), with its extends-chain down to base."""
    roots = roots if roots is not None else pack_roots()
    dirs, chain, data = [], [], {}
    cur: str | None = name
    while cur:
        if cur in chain:
            raise VeditError(f"style {name!r}: extends loops through {cur!r}")
        chain.append(cur)
        d = _pack_dir(cur, roots)
        dirs.append(d)
        cur = read_yaml(d).get("extends") or (BASE if cur != BASE else None)
    for d in reversed(dirs):
        data = _merge(data, read_yaml(d))
    data["name"] = name
    font = data.get("font")
    if isinstance(font, dict) and "ui" not in font and "text" in font:
        font["ui"] = font["text"]  # the small UI lines follow the text font unless the pack sets `ui`
    return Pack(name, dirs, data)


# ---- validation ----


def _kind_ok(kind: str, v) -> bool:
    if kind == "bool":
        return isinstance(v, bool)
    if kind == "number":
        return isinstance(v, int | float) and not isinstance(v, bool)
    if kind == "list":
        return isinstance(v, list) and all(isinstance(x, str) for x in v)
    if kind == "beats":
        return isinstance(v, dict) and all(isinstance(x, str) for x in v.values())
    if kind == "box":
        return (
            isinstance(v, list)
            and len(v) == 4
            and all(isinstance(x, int | float) and not isinstance(x, bool) for x in v)
            and v[2] > 0
            and v[3] > 0
        )
    if kind == "scene":
        return isinstance(v, str | dict)
    return isinstance(v, str | int | float) and not isinstance(v, bool)


def check_fields(tpl: TypeTemplate, fields: dict, where: str, logos: dict | None = None) -> list[str]:
    """Problems with a cue's fields against its type's slots (empty list = valid)."""
    errs = []
    for k, v in fields.items():
        if k in CUE_KEYS:
            continue
        if k not in tpl.slots:
            close = difflib.get_close_matches(k, list(tpl.slots) + sorted(CUE_KEYS), n=1)
            hint = f"; did you mean {close[0]!r}?" if close else ""
            errs.append(
                f"{where}: unknown field {k!r} for type {tpl.name} (slots: {', '.join(tpl.slots)}){hint}"
            )
            continue
        s = tpl.slots[k]
        if not _kind_ok(s.kind, v):
            errs.append(f"{where}: {k!r} should be {s.kind}, got {type(v).__name__}")
        elif s.kind == "logo" and logos is not None and str(v) not in logos:
            errs.append(f"{where}: logo {v!r} is not in the style (logos: {', '.join(sorted(logos))})")
    for s in tpl.slots.values():
        if s.required and s.name not in fields:
            errs.append(f"{where}: type {tpl.name} needs {s.name!r}")
    return errs


def check(pk: Pack) -> list[str]:
    """Every problem of a loaded pack at once (empty = good). See vedit/graphics/packcheck.py."""
    from vedit.graphics.packcheck import check as _check

    return _check(pk)


# ---- template engine (mustache subset) ----

_TAG = re.compile(r"\{\{([#^/&]?)\s*([\w.\-]+)\s*\}\}")


def _lookup(stack: list, name: str):
    if name == ".":
        return stack[-1]
    head, *rest = name.split(".")
    for ctx in reversed(stack):
        if isinstance(ctx, dict) and head in ctx:
            v = ctx[head]
            for part in rest:
                v = v.get(part) if isinstance(v, dict) else None
            return v
    return None


def _section_end(tpl: str, name: str, start: int) -> tuple[int, int]:
    depth = 1
    for m in _TAG.finditer(tpl, start):
        if m.group(2) != name:
            continue
        if m.group(1) in "#^" and m.group(1):
            depth += 1
        elif m.group(1) == "/":
            depth -= 1
            if depth == 0:
                return m.start(), m.end()
    raise VeditError(f"template: section {name!r} is not closed")


def _str(v) -> str:
    if v is None or v is False:
        return ""
    if isinstance(v, float):
        return f"{v:.3f}".rstrip("0").rstrip(".")
    return str(v)


def _render(tpl: str, stack: list) -> str:
    out, pos = [], 0
    while True:
        m = _TAG.search(tpl, pos)
        if not m:
            out.append(tpl[pos:])
            return "".join(out)
        out.append(tpl[pos : m.start()])
        op, name = m.group(1), m.group(2)
        if op in ("#", "^"):
            inner_end, close_end = _section_end(tpl, name, m.end())
            inner = tpl[m.end() : inner_end]
            v = _lookup(stack, name)
            if op == "^":
                if not v:
                    out.append(_render(inner, stack))
            elif isinstance(v, list):
                out.extend(_render(inner, [*stack, item]) for item in v)
            elif isinstance(v, dict):
                out.append(_render(inner, [*stack, v]))
            elif v:
                out.append(_render(inner, stack))
            pos = close_end
        elif op == "/":
            raise VeditError(f"template: unexpected close {{{{/{name}}}}}")
        else:
            v = _str(_lookup(stack, name))
            out.append(v if op == "&" else html.escape(v, quote=True))
            pos = m.end()


def render(tpl: str, ctx: dict) -> str:
    return _render(tpl, [ctx])


def syntax(tpl: str) -> list[str]:
    """Section tags that do not pair up, found without rendering (so skipped sections are checked too)."""
    errs, stack = [], []
    for m in _TAG.finditer(tpl):
        op, name = m.group(1), m.group(2)
        if op in ("#", "^") and op:
            stack.append(name)
        elif op == "/":
            if not stack:
                errs.append(f"unexpected close {{{{/{name}}}}}")
            elif stack[-1] != name:
                errs.append(f"{{{{/{name}}}}} closes {{{{#{stack[-1]}}}}}")
                stack.pop()
            else:
                stack.pop()
    errs += [f"section {n!r} is not closed" for n in stack]
    return errs
