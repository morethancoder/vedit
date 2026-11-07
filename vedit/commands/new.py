"""vedit new: create a project folder (project.yaml, src/ links, templates) and build its ingest media."""

import argparse
import re
import string
import time
from pathlib import Path

import yaml

from vedit import channel as chan
from vedit import state
from vedit.ingest import cap as capmod
from vedit.ingest.media import SourcePlan, ingest_media
from vedit.project import Paths, Project
from vedit.report import Report, VeditError
from vedit.run import ffprobe_duration, log_path

EPILOG = "example: vedit new <cap-project> --lang ar --dialect iq --style yellow-doodle"
DEFAULT_PARENT = "~/Demos"

CUTS_TEMPLATE = """\
# cuts.yaml: what to remove or mark. Written by you after reading the transcript. `vedit guide cuts`.
#
# cuts:
#   - near: A 245.0           # source clip + approx time (from the transcript)
#     say: "words to remove"  # matched with Arabic normalisation
#     why: filler-repeat
# pins:
#   - near: A 300.2
#     in: 300.18
#     out: 301.06
# chapters:
#   - near: A 230.0
#     title: "Chapter title"
# end: last-word
cuts: []
pins: []
chapters: []
"""

CUES_TEMPLATE = """\
# cues.yaml: graphics anchored to spoken words. `vedit guide cues`.
#
# style: yellow-doodle          # default for every cue
# cues:
#   - type: label
#     at: "words spoken"
#     text: "Label text"
cues: []
"""


def add_args(sp) -> None:
    sp.add_argument("inputs", nargs="+", metavar="input", help=argparse.SUPPRESS)
    sp.usage = "vedit new <cap|export|video>... [options]"
    sp.add_argument("--slug", help="folder name (default: from the input)")
    sp.add_argument("--lang", choices=project_langs(), metavar="ar|en", help="spoken language")
    sp.add_argument("--dialect", metavar="D", help="ar dialect: iq, gulf, lev, eg, ma, msa")
    sp.add_argument("--style", metavar="S", help="style pack (default: from channel/config)")
    sp.add_argument("--channel", metavar="H", help="channel handle (default: config.yaml)")
    sp.add_argument("--hint", metavar="TEXT", help="names to favour in transcription")
    sp.add_argument("--dir", default=DEFAULT_PARENT, metavar="PARENT", help="parent folder (~/Demos)")
    sp.epilog = EPILOG


def project_langs() -> list[str]:
    from vedit.project import LANGS

    return list(LANGS)


def slugify(text: str) -> str:
    return re.sub(r"[^\w]+", "-", text.lower(), flags=re.UNICODE).strip("-_") or "project"


def _in_git_tree(path: Path) -> Path | None:
    for d in (path, *path.parents):
        if (d / ".git").exists():
            return d
    return None


def _classify(inputs: list[str]) -> tuple[capmod.CapProject | None, list[Path], str]:
    """(cap, files, slug base). A cap project has `files == [export]`."""
    paths = [Path(i).expanduser().resolve() for i in inputs]
    for p in paths:
        if not p.exists():
            raise VeditError(f"{p} does not exist", next="vedit new <cap-project-or-video> ...")
    first = paths[0]
    if first.is_dir():
        if len(paths) > 1:
            raise VeditError("a .cap folder is a whole project: pass it alone", next="vedit new <cap>")
        cap = capmod.read_cap(first)
        if cap.export is None:
            raise VeditError(
                f"{cap.path} has no exported video (output/result.mp4)",
                next="export it in Cap, then rerun vedit new",
            )
        return cap, [cap.export], slugify(cap.pretty_name)
    if len(paths) == 1:
        try:
            cap = capmod.read_cap(capmod.find_cap_for_export(first))
        except capmod.CapError:
            cap = None
        if cap is not None:
            return cap, [first], slugify(first.stem)
    for p in paths:
        if not p.is_file():
            raise VeditError(f"{p} is not a video file")
    if len(paths) > len(string.ascii_uppercase):
        raise VeditError("too many sources (max 26)")
    return None, paths, slugify(first.stem)


def _link(link: Path, target: Path) -> None:
    if link.is_symlink() and link.resolve() == target.resolve():
        return
    if link.exists() or link.is_symlink():
        raise VeditError(f"{link} exists and points elsewhere", next=f"remove {link} and rerun vedit new")
    link.symlink_to(target)


def _resolve_settings(ns, r: Report) -> dict:
    handle = ns.channel or chan.default_channel()
    ch = chan.load_channel(handle)
    if handle and ch is None:
        r.warn(
            f"channel '{handle}' has no channel.yaml in {chan.config_dir() / 'channels' / handle}; continuing"
        )
        ch = {}
    ch = ch or {}
    lang = ns.lang or ch.get("lang")
    if not lang:
        raise VeditError(
            "no language: pass --lang ar|en or set `lang:` in the channel's channel.yaml",
            next="vedit new <input> --lang ar --dialect iq",
        )
    same_lang = not ch.get("lang") or ch["lang"] == lang
    dialect = ns.dialect or (ch.get("dialect") if same_lang else None)
    hint = ns.hint or ch.get("hint")
    return {"lang": lang, "dialect": dialect, "channel": handle, "style": ns.style, "hint": hint}


def _write_project(root: Path, slug: str, cfg: dict, sources: dict) -> None:
    data = {"slug": slug, "lang": cfg["lang"]}
    for k in ("dialect", "channel", "style", "hint"):
        if cfg.get(k):
            data[k] = cfg[k]
    data["sources"] = sources
    (root / "project.yaml").write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )


def _warn_differences(project: Project, cfg: dict, r: Report) -> None:
    for k in ("lang", "dialect", "channel", "style", "hint"):
        if cfg.get(k) and getattr(project, k) != cfg[k]:
            r.warn(
                f"project.yaml keeps {k}: {getattr(project, k)!r}; this run asked for {cfg[k]!r} (edit it by hand)"
            )


def run(ns) -> Report:
    r = Report("new")
    cap, files, base = _classify(ns.inputs)
    cfg = _resolve_settings(ns, r)
    slug = ns.slug or base
    parent = Path(ns.dir).expanduser().resolve()
    root = parent / slug
    if (hit := _in_git_tree(root)) is not None:
        raise VeditError(
            f"{root} is inside a git work tree ({hit}): projects never live in a code repo",
            next="vedit new <input> --dir ~/Demos",
        )
    paths = Paths(root)
    existed = paths.project_yaml.is_file()
    root.mkdir(parents=True, exist_ok=True)
    paths.src.mkdir(exist_ok=True)
    paths.custom.mkdir(exist_ok=True)
    paths.ensure()

    sources: dict = {}
    plans: list[SourcePlan] = []
    for i, f in enumerate(files):
        name = string.ascii_uppercase[i]
        if cap is not None:
            _link(paths.src / f"{name}{f.suffix}", f)
            _link(paths.src / f"{name}-camera{cap.camera.suffix}", cap.camera)
            sources[name] = {"cap": str(cap.path), "camera": "raw"}
        else:
            _link(paths.src / f"{name}{f.suffix}", f)
            sources[name] = {"file": f"src/{name}{f.suffix}"}
        plans.append(SourcePlan(name, file=f, cap=cap))

    if existed:
        project = Project.load(root)
        _warn_differences(project, cfg, r)
    else:
        _write_project(root, slug, cfg, sources)
        for tpl, text in ((paths.cuts, CUTS_TEMPLATE), (paths.cues, CUES_TEMPLATE)):
            if not tpl.exists():
                tpl.write_text(text, encoding="utf-8")
        project = Project.load(root)

    t0 = time.monotonic()
    try:
        outputs, built, warns = ingest_media(paths, plans, log_path(root, "new"))
    except VeditError as e:
        e.next = e.next or f"see {log_path(root, 'new')}; fix the cause and rerun vedit new"
        raise
    for w in warns:
        r.warn(w)
    project = Project.load(root)
    inputs = state.current_inputs(project, paths, state.load(paths)["stages"])["ingest"]
    state.record_stage(paths, "ingest", inputs or "", outputs)

    r.step(f"{slug}  ({root})")
    r.ok_("created" if not existed else "existing project kept")
    for k in ("style", "accent"):
        val, origin = (chan.effective_style if k == "style" else chan.effective_accent)(project)
        if val:
            r.info(f"{k} {val} (from {origin})")
    durations = {}
    for p in plans:
        d = ffprobe_duration(p.file)
        durations[p.name] = round(d, 2)
        r.info(
            f"source {p.name}: {p.file.name}  {d:.1f}s" + ("  (cap: raw camera on Cap trims)" if cap else "")
        )
    r.info(
        f"media: {len(built)} built, {len(outputs) - len(built)} already done  ({time.monotonic() - t0:.0f}s)"
    )
    r.data = {
        "project": str(root),
        "sources": {n: str(s.get("cap") or root / s["file"]) for n, s in sources.items()},
        "durations": durations,
        "outputs": [str(o) for o in outputs],
        "built": built,
        "created": not existed,
    }
    r.next = f"cd {root} && vedit transcribe"
    return r
