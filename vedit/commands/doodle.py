"""vedit doodle: list the doodle scene library; `preview` renders one scene (or an inline spec file) as a short
1080p draft MP4 with its beats spaced evenly, in a style pack, to check the drawing before a cue uses it.

Output: `<project>/.vedit/doodles/` inside a project, else `<config_dir>/cache/doodles/`.
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace

import yaml

from vedit import channel as chan
from vedit.doodles import library, spec
from vedit.graphics import compose, pages
from vedit.graphics import pack as packs
from vedit.graphics.cues import Cue
from vedit.graphics.plan import Placement
from vedit.project import Project, ProjectError, find_project
from vedit.render.hf import render_cmd
from vedit.report import Report, VeditError
from vedit.run import run as sh

EPILOG = "example: vedit doodle preview flood --style base"
BEAT_GAP = 1.7  # seconds between evenly spaced beats in a preview
TAIL = 3.0  # seconds after the last beat: the evenly spaced beats end there (spec.resolve_beats)


def add_args(sp) -> None:
    sp.add_argument("action", choices=["list", "preview"], help="list the library, or preview one scene")
    sp.add_argument("scene", nargs="?", help="library scene name, or a .yaml file holding an inline spec")
    sp.add_argument("--style", metavar="PACK", help="style pack (default: project's, config's, else base)")
    sp.add_argument("--lang", metavar="LANG", help="short-form row direction (default: project's, else ar)")
    sp.epilog = EPILOG


def _project(override: str | None):
    """The project around cwd (or --project), else None: a preview works outside a project too."""
    try:
        return Project.load(find_project(override=override))
    except ProjectError:
        if override:
            raise
        return None


def _scene(arg: str):
    """(name, scene value): a library name, or the spec in a YAML file (top level or under `scene:`)."""
    f = Path(arg).expanduser()
    if arg.endswith((".yaml", ".yml")):
        if not f.is_file():
            raise VeditError(f"{f}: not found", next="vedit guide cue-doodle")
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        value = data.get("scene", data) if isinstance(data, dict) else data
        errs = spec.check(value, f.name)
        if errs:
            raise VeditError("\n".join(errs), next="vedit guide cue-doodle")
        return f.stem, value
    library.scene(arg)  # raises with the closest name
    return arg, arg


def _list() -> Report:
    r = Report("doodle")
    rows = []
    for n in library.names():
        sp = library.scene(n)
        rows.append(
            {"name": n, "lang": sp.get("lang"), "beats": spec.beat_names(sp), "about": sp.get("about", "")}
        )
        r.info(f"{n:11s} {sp.get('lang', ''):3s} beats: {', '.join(spec.beat_names(sp))}")
    r.data = {"scenes": rows}
    r.next = "vedit doodle preview <scene>"
    return r


def index_html(cid: str, dur: float, pk) -> str:
    return f"""<!doctype html>
<html>
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="assets/gsap.min.js"></script>
    <style>
{pages.font_faces(pk)}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ width: 1920px; height: 1080px; overflow: hidden; background: #17140f; }}
      #root {{ position: relative; width: 100%; height: 100%; overflow: hidden;
        background: radial-gradient(ellipse at 40% 45%, #3a332a 0%, #1d1a15 55%, #0f0d0a 100%); }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{dur:.3f}" data-width="1920" data-height="1080">
      <div id="{cid}" class="clip" data-composition-id="{cid}" data-composition-src="compositions/{cid}.html" data-start="0" data-duration="{dur:.3f}" data-track-index="1" data-width="1920" data-height="1080"></div>
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""


def build_preview(name: str, value, pk, out: Path, lang: str) -> tuple[Path, float]:
    """Write the preview HyperFrames project under `out`; (project dir, seconds)."""
    sp, _ = library.resolve(value, lang=lang)
    n = len(spec.beat_names(sp))
    dur = round(
        0.12 + BEAT_GAP * max(n - 1, 0) + TAIL, 2
    )  # spec.resolve_beats spaces beats over [0.12, D - 3]
    slug = re.sub(r"[^a-z0-9-]+", "-", f"{name}-{pk.name}".lower()).strip("-")
    hf = out / slug
    cid = "dz-preview"
    cue = Cue(cid, "doodle", pk.name, {"scene": value, "beats": {}}, "A", 0.0, 0.0, dur)
    env = pages.Env(SimpleNamespace(root=hf, custom=hf / "custom"), lang)
    pg = pages.render(Placement(cue, 0.0, dur, 6), pk, env)
    compose.write_if_changed(hf / "compositions" / f"{cid}.html", pg.html)
    compose.write_if_changed(hf / "index.html", index_html(cid, dur, pk))
    compose.assets(hf, [pk], env, set())
    return hf, dur


def run(ns) -> Report:
    if ns.action == "list":
        return _list()
    if not ns.scene:
        raise VeditError("which scene? vedit doodle preview <scene>", next="vedit doodle list")
    try:
        project = _project(ns.project)
    except ProjectError as e:
        raise VeditError(str(e), next="vedit doodle preview <scene>  (outside a project is fine too)") from e
    style = ns.style or (
        chan.style_choice(project)[0] if project else chan.load_config().get("style") or "base"
    )
    pk = packs.load(style)
    probs = packs.check(pk)
    if probs:
        raise VeditError(f"style {style!r} has problems:\n  " + "\n  ".join(probs), next="vedit styles")
    lang = ns.lang or (project.lang if project else "ar")
    out = project.paths.vedit / "doodles" if project else chan.config_dir() / "cache" / "doodles"
    name, value = _scene(ns.scene)
    hf, dur = build_preview(name, value, pk, out, lang)
    mp4 = out / f"{hf.name}.mp4"
    log = (project.paths.vedit if project else out) / "logs" / "doodle.log"
    sh(render_cmd(hf, mp4), timeout=600, cwd=hf, log=log)
    r = Report("doodle")
    r.ok_(f"{name} in {style}: {dur:g}s, beats every {BEAT_GAP:g}s")
    r.info(str(mp4))
    r.data = {"scene": name, "style": style, "mp4": str(mp4), "seconds": dur, "project": str(hf)}
    r.next = f"open -a 'QuickTime Player' {mp4}"
    return r
