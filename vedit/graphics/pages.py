"""One HyperFrames sub-composition per graphic: the engine's context + the pack's type template (T build.py `page`).

The look lives in the pack (`types/<type>.html`, `partials/*.html`, pack.yaml tokens); this module only computes
what the engine knows and hands it over as template context. Context every template gets:

    id, type, dur (seconds), side ("left"|"right"), left/right (bools), dir ("rtl"|"ltr"), theme ("dark"|"light"),
    th.<token> (the theme's colours; th.shadow is the pack's busy_shadow over busy screens), blur (bool),
    c.<colour>, font.text|ui|mono|hand, m.<motion token> (pack.yaml `motion`: m.ease_in, m.ease_out, m.ease_draw,
    m.ease_pop, m.in, m.out, m.out_lead, m.scene_out, m.scene_lead, m.stagger, m.rise), logo.html (inline mark, raw) + logo.spin, part.<partial> (raw), and the cue's
    own fields by slot name (`{{title}}`). In scripts `D` is the duration and `q`/`qa` query inside the graphic.

Per type: kinetic `words[] {w, hl, at}` + `width` (px column beside the face); chip `toks[]`, `n_toks`,
`code_rtl`; big-number `big.{left, top, fs, width, tuck, track, pre_fs, wrap_top, wrap_w}` + `color`;
doodle `beats[] {name, at}` + `doodle.{svg, labels, draw, fill, lab, float, spin, fade_at, font}`
(vedit/doodles/library.py `drawn`); screen `video.{src, from, w, h, top}` + `steps[] {n, text}`; plug
`plug.{name, kicker, url, trial, logo, demo, demo_dur, hold}` + `url_at`, `click_at`, `free_at`.
Times in context are seconds into the graphic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from vedit.doodles import library as doodle_library
from vedit.graphics import pack as packs
from vedit.graphics.faces import proxy_of
from vedit.report import VeditError
from vedit.run import ffprobe_duration, ffprobe_json, hash_of, sample_hash

# part of every composition key: an engine change regenerates everything (pages, the pack template engine, the
# doodle drawing code)
ENGINE = [Path(__file__), Path(packs.__file__), *sorted(Path(doodle_library.__file__).parent.glob("*.py"))]
NBSP = " "
KINETIC_COL = 720  # T's column when the plan gives none (centred lines)
PLUG_KEYS = {"name", "kicker", "url", "trial", "logo", "demo", "hold"}
EXIT_LEAD = 0.75  # seconds before the end that a kinetic line starts to leave
RTL_LANGS = {"ar", "fa", "ur", "he"}
SCREEN = {"h": 880, "max_w": 1100, "top": 100}  # T broll2: 880 px tall window right of the text column


@dataclass
class Env:
    """What every page needs from the project, gathered once per build."""

    paths: object
    lang: str = "ar"
    accent: str | None = None
    plug: str | None = None
    slug: str = ""
    custom_logos: dict[str, Path] = field(default_factory=dict)


@dataclass
class Page:
    html: str
    sounds: list[tuple[str, float]]  # (sfx kind, seconds into the graphic)
    media: dict[str, Path]  # hf-relative path -> file to link there


# ---- context ----


def theme(pk, name: str, blur: bool, accent: str | None) -> dict:
    th = dict(pk.data.get("themes", {}).get(name) or {})
    if blur and name == "dark" and pk.data.get("busy_shadow"):
        th["shadow"] = pk.data["busy_shadow"]
    base = pk.data.get("colors", {}).get("accent")
    if accent and base:
        th = {k: (accent if str(v).lower() == str(base).lower() else v) for k, v in th.items()}
    return th


def colors(pk, accent: str | None) -> dict:
    c = dict(pk.data.get("colors") or {})
    if accent:
        c["accent"] = accent
    return c


_VAR = re.compile(r"var\(--([\w-]+)\s*,\s*([^)]*)\)")


def logo(name: str | None, pk, env: Env, th: dict) -> dict:
    """Inline SVG for a pack mark (its `var(--x, ...)` fills resolved from the theme), <img> for a project one."""
    if not name:
        return {"html": "", "spin": False}
    spin = name in (pk.data.get("logo_motion") or {}).get("spin", [])
    if name in env.custom_logos:
        f = env.custom_logos[name]
        return {"html": f'<img class="logo" src="assets/logos/{f.name}" alt="" />', "spin": spin}
    f = pk.logos().get(name)
    if f is None:
        return {"html": "", "spin": False}
    svg = _VAR.sub(lambda m: str(th.get(m.group(1), m.group(2).strip())), f.read_text())
    svg = re.sub(r"<\?xml.*?\?>\s*", "", svg).strip()
    return {"html": re.sub(r"<svg\b", '<svg class="logo"', svg, count=1), "spin": spin}


def font_faces(pk) -> str:
    out = []
    for f in pk.data.get("fonts") or []:
        name = Path(f["file"]).name
        fmt = "woff2" if name.endswith(".woff2") else "truetype"
        out.append(
            f'      @font-face {{ font-family: "{f["family"]}"; src: url("assets/fonts/{name}") '
            f'format("{fmt}"); font-weight: {f.get("weight", 400)}; font-style: {f.get("style", "normal")}; }}'
        )
    return "\n".join(out)


def partials(pk, ctx: dict) -> dict[str, str]:
    out = {}
    for name, f in pk.partials().items():
        t = packs._parse_template(name, f)
        body = re.sub(r"<!--.*?-->", "", t.body, flags=re.DOTALL).strip()
        out[name] = packs.render(t.style + t.script + body, ctx)
    return out


def base_context(p, pk, env: Env) -> dict:
    cue = p.cue
    dark_only = cue.type in ("chapter", "doodle", "screen", "plug")  # over blurred/dimmed or busy footage
    th_name = "dark" if dark_only else p.theme
    th = theme(pk, th_name, p.blur, env.accent)
    ctx = {k: v for k, v in cue.fields.items()}
    side = p.side or "left"
    ctx.update(
        id=cue.id,
        type=cue.type,
        dur=round(p.dur, 3),
        side=side,
        left=side == "left",
        right=side == "right",
        dir="rtl" if env.lang.split("-")[0].lower() in RTL_LANGS else "ltr",
        theme=th_name,
        th=th,
        blur=p.blur and cue.type in ("label", "chip", "kinetic"),
        c=colors(pk, env.accent),
        font=pk.data.get("font") or {},
        m=pk.data.get("motion") or {},
        logo=logo(cue.fields.get("logo"), pk, env, th),
    )
    return ctx


# ---- per type ----


def kinetic_times(p, n: int) -> tuple[list[float], int]:
    """Seconds into the graphic at which each of `n` words appears, and how many were squeezed before the exit."""
    sp = [max(0.05, round(t - p.start, 2)) for t in p.cue.spoken]
    if sp:
        times = (sp + [sp[-1] + 0.25 * (k + 1) for k in range(n)])[:n]
    else:  # T: words not found, evenly spaced
        times = [round(0.2 + k * min(0.35, (p.dur - 1) / max(n, 1)), 2) for k in range(n)]
    limit = max(0.05, round(p.dur - EXIT_LEAD, 2))  # the exit starts there: no word may land after it
    late = sum(t > limit for t in times)
    return [min(t, limit) for t in times], late  # order kept; the late ones appear together at the limit


def _kinetic(p, ctx: dict) -> list[tuple[str, float]]:
    words = str(ctx["words"]).split(" ")  # not split(): a non-breaking space keeps two words together (T)
    words = [w for w in words if w]
    hl = set()
    subs = [(i, s) for i, w in enumerate(words) for s in w.split(NBSP)]
    for phrase in ctx.get("highlight") or []:
        want = phrase.replace(NBSP, " ").split()
        for k in range(len(subs) - len(want) + 1):
            if [s for _, s in subs[k : k + len(want)]] == want:
                hl |= {i for i, _ in subs[k : k + len(want)]}
    times = kinetic_times(p, len(words))[0]
    ctx["words"] = [{"w": w, "hl": i in hl, "at": times[i]} for i, w in enumerate(words)]
    ctx["width"] = p.width or KINETIC_COL
    return [("kinetic", 0.08)]


def _chip(p, ctx: dict) -> list[tuple[str, float]]:
    code = str(ctx["code"])
    rtl = bool(re.search(r"[؀-ۿ]", code))
    ctx["toks"] = re.findall(r"\S+\s*", code) if rtl else list(code)
    ctx["n_toks"], ctx["code_rtl"] = len(ctx["toks"]), rtl
    if not ctx["logo"]["html"]:
        ctx["logo"] = ctx["_logo_default"]
    return [("chip", 0.08)]


def _big(p, ctx: dict, pk) -> list[tuple[str, float]]:
    b = dict(p.big)
    pre_fs = max(44, round(b["fs"] * 0.22))
    b.update(
        pre_fs=pre_fs,
        wrap_top=b["top"] - pre_fs - 6,
        wrap_w=b["width"] + 40,
        track=(pk.data.get("big") or {}).get("track", -0.03),
    )
    ctx["big"] = b
    col = str(ctx.get("color") or "").strip()
    # `accent` (or any pack colour name) follows the style, so switching packs needs no cue edit
    ctx["color"] = ctx["c"].get(col) if col in ctx["c"] else (col or ctx["c"].get("ivory", "#FAF9F5"))
    return [("big-number", 0.1)]


def _doodle(p, ctx: dict, pk, env: Env) -> list[tuple[str, float]]:
    beats = sorted(((t, name) for name, t in p.cue.beats.items()), key=lambda x: x[0])
    ctx["beats"] = [{"name": name, "at": round(max(0.3, t - p.start), 2)} for t, name in beats]
    local = {name: t - p.start for name, t in p.cue.beats.items()}  # T: unheard beats are spaced evenly
    ctx["doodle"] = doodle_library.drawn(ctx["scene"], p.dur, local, pk, env.accent, env.lang)
    return [("focus", 0.0)] + [("beat", b["at"]) for b in ctx["beats"]]


def _screen(p, ctx: dict, env: Env, media: dict) -> list[tuple[str, float]]:
    src = proxy_of(env.paths, str(ctx["source"]))
    if not src.is_file():
        raise VeditError(
            f"{p.id}: no proxy for source {ctx['source']!r} ({src})", next="vedit new  (rebuilds media)"
        )
    vs = next(s for s in ffprobe_json(src)["streams"] if s["codec_type"] == "video")
    aspect = int(vs["width"]) / int(vs["height"])
    h = SCREEN["h"]
    w = round(h * aspect)
    if w > SCREEN["max_w"]:
        w, h = SCREEN["max_w"], round(SCREEN["max_w"] / aspect)
    rel = f"media/src-{ctx['source']}{src.suffix}"
    media[rel] = src
    ctx["video"] = {
        "src": rel,
        "from": float(ctx.get("from") or 0.0),
        "w": w,
        "h": h,
        "top": round((1080 - h) / 2),
    }
    ctx["steps"] = [{"n": i + 1, "text": s} for i, s in enumerate(ctx.get("steps") or [])]
    return [("focus", 0.0)]


def plug_dir(env: Env) -> Path:
    """The folder the plug preset comes from: the project's `custom/plug/` when it has a plug.yaml, else the
    project's channel's `plug/` when that has one, else the project's (maybe missing) folder."""
    from vedit import channel as chan

    d = Path(env.paths.custom) / "plug"
    handle = None if (d / "plug.yaml").is_file() else chan.project_channel(env.paths.root)
    if handle and (chan.config_dir() / "channels" / handle / "plug" / "plug.yaml").is_file():
        d = chan.config_dir() / "channels" / handle / "plug"
    return d


def plug_preset(env: Env) -> tuple[dict, dict[str, Path]]:
    """The plug preset: the project's `custom/plug/plug.yaml` (+ its files), else the project's channel's
    `<config_dir>/channels/<handle>/plug/plug.yaml`, else brand text only (project.yaml `plug`).
    The project's folder replaces the channel's whole, files included."""
    d = plug_dir(env)
    f = d / "plug.yaml"
    data = (yaml.safe_load(f.read_text()) or {}) if f.is_file() else {}
    bad = sorted(set(data) - PLUG_KEYS)
    if bad:
        raise VeditError(f"{f}: unknown key(s) {', '.join(bad)} (keys: {', '.join(sorted(PLUG_KEYS))})")
    out = {"name": data.get("name") or env.plug or env.slug}
    files = {}
    for k in ("kicker", "url", "trial"):
        if data.get(k):
            out[k] = str(data[k])
    for k in ("logo", "demo", "hold"):
        if data.get(k):
            src = d / str(data[k])
            if not src.is_file():
                raise VeditError(f"{f}: {k} file {src} not found")
            rel = f"media/plug-{src.name}"
            files[rel], out[k] = src, rel
    return out, files


def _plug(p, ctx: dict, env: Env, media: dict) -> list[tuple[str, float]]:
    pl, files = plug_preset(env)
    media.update(files)
    if pl.get("demo"):
        pl["demo_dur"] = round(ffprobe_duration(files[pl["demo"]]), 3)
    t = p.cue.times
    url_at = round(t["url"] - p.start, 2) if "url" in t else round(p.dur * 0.55, 2)
    ctx.update(
        plug=pl,
        url_at=url_at,
        click_at=round(url_at + 1.35, 2),
        free_at=round(t["trial"] - p.start, 2) if "trial" in t else round(url_at + 2.4, 2),
    )
    sounds = [("phone", 0.1)] if pl.get("demo") else []
    return sounds + ([("url", ctx["click_at"])] if pl.get("url") else [])


# ---- the page ----


def page(cid: str, faces: str, css: str, body: str, script: str, size: tuple[int, int] = (1920, 1080)) -> str:
    """The sub-composition shell (HyperFrames contract: everything inside <template>, one paused timeline)."""
    return f"""<!doctype html>
<html>
  <head><meta charset="UTF-8" /></head>
  <body>
    <template>
      <style>
{faces}
{css.strip(chr(10))}
      </style>
      <div id="root" data-composition-id="{cid}" data-width="{size[0]}" data-height="{size[1]}">
{body.strip(chr(10))}
      </div>
      <script>
        const tl = gsap.timeline({{ paused: true }});
        const q = (s) => document.querySelector('[data-composition-id="{cid}"] ' + s);
        const qa = (s) => document.querySelectorAll('[data-composition-id="{cid}"] ' + s);
        const D = DUR;
{script.strip(chr(10))}
        window.__timelines["{cid}"] = tl;
      </script>
    </template>
  </body>
</html>
"""


def vedit_vars(p, pk, env: Env) -> str:
    """The pack's tokens as CSS variables on a custom graphic's host, plus the pack's @font-face rules:
    --vedit-<colour> (every `colors` key, accent per channel), --vedit-<theme token> (text, sub, kicker, shadow...
    from the dark theme), --vedit-font-<key> (every `font` key)."""

    def name(k: str) -> str:
        return str(k).replace("_", "-")

    rows = {f"--vedit-{name(k)}": v for k, v in colors(pk, env.accent).items()}
    rows.update({f"--vedit-{name(k)}": v for k, v in theme(pk, "dark", False, env.accent).items()})
    rows.update({f"--vedit-font-{name(k)}": v for k, v in (pk.data.get("font") or {}).items()})
    decl = "\n".join(f"        {k}: {v};" for k, v in rows.items())
    return (
        f'      <style>\n{font_faces(pk)}\n      [data-composition-id="{p.id}"] {{\n{decl}\n      }}\n'
        "      </style>\n"
    )


def custom_page(p, pk, env: Env) -> str:
    """A custom cue: the project's own sub-composition, its composition id set to the cue id, with the pack's
    tokens (vedit_vars) in a style block before its own."""
    root = Path(env.paths.root).resolve()
    f = (root / str(p.cue.fields["file"])).resolve()
    if not f.is_relative_to(root):
        raise VeditError(
            f"{p.id}: file {p.cue.fields['file']!r} is outside the project", next="vedit guide cue-custom"
        )
    text = f.read_text(encoding="utf-8")
    m = re.search(r'data-composition-id\s*=\s*"([^"]+)"', text)
    if not m or "<template" not in text:
        raise VeditError(
            f"{p.id}: {f} is not a sub-composition (needs <template> with a data-composition-id root)",
            next="vedit guide cue-custom",
        )
    old = m.group(1)
    for a, b in ((f'"{old}"', f'"{p.id}"'), (f"'{old}'", f"'{p.id}'")):
        text = text.replace(a, b)
    return re.sub(r"<template[^>]*>", lambda m: m.group(0) + "\n" + vedit_vars(p, pk, env), text, count=1)


def render(p, pk, env: Env, size: tuple[int, int] = (1920, 1080), extra_css: str = "") -> Page:
    """The finished sub-composition of one placement; `size` and `extra_css` place it in another output's frame
    (vedit.formats.layout)."""
    media: dict[str, Path] = {}
    if p.cue.type == "custom":
        return Page(custom_page(p, pk, env), [], media)
    ctx = base_context(p, pk, env)
    ctx["_logo_default"] = logo("spark", pk, env, ctx["th"])
    typ = p.cue.type
    if typ == "kinetic":
        sounds = _kinetic(p, ctx)
    elif typ == "chip":
        sounds = _chip(p, ctx)
    elif typ == "big-number":
        sounds = _big(p, ctx, pk)
    elif typ == "doodle":
        sounds = _doodle(p, ctx, pk, env)
    elif typ == "screen":
        sounds = _screen(p, ctx, env, media)
    elif typ == "plug":
        sounds = _plug(p, ctx, env, media)
    elif typ == "label":
        sounds = [("label", 0.08)]
    else:  # chapter: silent (T: no sound on the chapter breaks)
        sounds = []
    ctx["part"] = partials(pk, ctx)
    tpl = pk.template(typ)
    css = packs.render(ctx["part"].get("base", "") + "\n" + tpl.style, ctx)
    if extra_css:
        css += "\n/* output layout (vedit.formats.layout) */\n" + extra_css
    body = packs.render(tpl.body, ctx)
    script = packs.render(tpl.script, ctx)
    html = page(p.id, font_faces(pk), css, body, script, size).replace(
        "const D = DUR;", f"const D = {packs._str(ctx['dur'])};"
    )
    return Page(html, sounds, media)


def key(p, pk, env: Env, size: tuple[int, int] = (1920, 1080), extra_css: str = "") -> str:
    """Composition key: the cue, its placement, the pack files it is built from and the engine itself."""
    cue = p.cue
    parts: list = [
        *ENGINE,
        cue.key,
        [round(p.start, 3), round(p.dur, 3), p.side, p.theme, p.blur, p.width, p.big],
        *([list(size), extra_css] if (size != (1920, 1080) or extra_css) else []),
        [round(t, 3) for t in cue.spoken] if cue.type == "kinetic" else [],
        cue.beats,
        cue.times,
        env.lang,
        env.accent,
        cue.fields,
        *(
            [env.custom_logos.get("spark") or pk.logos().get("spark") or "spark"]
            if cue.type == "chip"
            else []
        ),
        *[d / "pack.yaml" for d in pk.dirs],
        *pk.partials().values(),
        pk.template(cue.type).path,
    ]
    lg = cue.fields.get("logo")
    if lg:
        parts.append(env.custom_logos.get(lg) or pk.logos().get(lg) or lg)
    if cue.type == "plug":
        d = plug_dir(env)
        parts += [env.plug, env.slug] + (
            [(f.name, sample_hash(f)) for f in sorted(d.iterdir())] if d.is_dir() else []
        )
    if cue.type == "screen":
        parts.append(sample_hash(proxy_of(env.paths, str(cue.fields["source"]))))
    if cue.type == "custom":
        parts += [env.accent, (Path(env.paths.root) / str(cue.fields["file"])).resolve()]
    if cue.type == "doodle":
        parts += doodle_library.key_parts(cue.fields.get("scene"), pk)
    return hash_of(*parts)
