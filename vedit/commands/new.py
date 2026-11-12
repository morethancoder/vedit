"""vedit new: create a project folder (project.yaml, src/ links, templates) and build its ingest media."""

import argparse
import re
import string
import time
from pathlib import Path

import yaml

from vedit import channel as chan
from vedit import importers, state
from vedit.ingest.media import ingest_media, plan_of
from vedit.project import Paths, Project, _source
from vedit.recording import Recording
from vedit.report import Report, VeditError
from vedit.run import ffprobe_duration, log_path

EPILOG = "example: vedit new talk.mp4 --lang en"

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
# style: base                   # default for every cue
# cues:
#   - type: label
#     at: "words spoken"
#     text: "Label text"
cues: []
"""


def add_args(sp) -> None:
    sp.add_argument("inputs", nargs="+", metavar="input", help=argparse.SUPPRESS)
    sp.usage = "vedit new <video|recording>... [options]"
    sp.add_argument("--slug", help="folder name (default: from the input)")
    sp.add_argument("--lang", choices=project_langs(), metavar="ar|en", help="spoken language")
    sp.add_argument("--dialect", metavar="D", help="ar dialect: iq, gulf, lev, eg, ma, msa")
    sp.add_argument("--style", metavar="S", help="style pack (default: from channel/config)")
    sp.add_argument("--channel", metavar="H", help="channel handle (default: config.yaml)")
    sp.add_argument("--hint", metavar="TEXT", help="names to favour in transcription")
    sp.add_argument(
        "--dir", metavar="PARENT", help="parent folder (default: config.yaml `projects:`, else here)"
    )
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


def _classify(inputs: list[str]) -> tuple[list[tuple[Path, Recording | None, str | None]], str]:
    """Each input as (path, what an importer read or None for a plain video, importer name); and the slug base."""
    paths = [Path(i).expanduser().resolve() for i in inputs]
    for p in paths:
        if not p.exists():
            raise VeditError(f"{p} does not exist", next="vedit new <video> ...")
    if len(paths) > len(string.ascii_uppercase):
        raise VeditError("too many sources (max 26)")
    out: list[tuple[Path, Recording | None, str | None]] = []
    for p in paths:
        hit = importers.recognise(p)
        if hit:
            imp, rec = hit
            if not Path(rec.video).is_file():
                raise VeditError(
                    f"{imp.name} importer: {p} has no edited video yet", next="export it, then rerun"
                )
            out.append((Path(rec.video).resolve(), rec, imp.name))
        elif p.is_file():
            out.append((p, None, None))
        else:
            raise VeditError(
                f"{p} is a folder no importer recognises",
                next="pass the video file, or add an importer for this recorder (vedit guide importers)",
            )
    first = out[0]
    return out, slugify(first[1].name if first[1] else first[0].stem)


def _parent(ns) -> Path:
    d = ns.dir or chan.load_config().get("projects")
    return Path(d).expanduser().resolve() if d else Path.cwd()


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
            next="vedit new <input> --lang en",
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
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=None, width=120),
        encoding="utf-8",
    )


def _warn_differences(project: Project, cfg: dict, r: Report) -> None:
    for k in ("lang", "dialect", "channel", "style", "hint"):
        if cfg.get(k) and getattr(project, k) != cfg[k]:
            r.warn(
                f"project.yaml keeps {k}: {getattr(project, k)!r}; this run asked for {cfg[k]!r} (edit it by hand)"
            )


def _sources(inputs: list, link) -> dict:
    """project.yaml `sources:`; link(name in src/, original) places the file and returns the path to write."""
    sources: dict = {}
    for i, (f, rec, imp) in enumerate(inputs):
        name = string.ascii_uppercase[i]
        spec: dict = {"file": link(f"{name}{f.suffix}", f)}
        if rec is not None and rec.camera is not None:
            cams = [link(f"{name}-camera{'' if k == 0 else f'-{k}'}{c.suffix}", c)
                    for k, c in enumerate(rec.camera.tracks)]  # fmt: skip
            spec["camera"] = cams[0] if len(cams) == 1 else cams
            spec["trims"] = [[t.track, t.start, t.end] for t in rec.camera.trims]
            spec["fps"] = rec.camera.fps
            if rec.camera.mirror:
                spec["mirror"] = True
        if rec is not None:
            if rec.origin:
                spec["origin"] = str(rec.origin)
            spec["importer"] = imp
        sources[name] = spec
    return sources


def _dry_run(r: Report, root: Path, paths: Paths, existed: bool, inputs: list) -> Report:
    """What `vedit new` would write and build, writing nothing."""
    if existed:
        plans = [plan_of(s) for s in Project.load(root).sources.values()]
        writes: list[str] = []
    else:
        links: list[str] = []
        specs = _sources(inputs, lambda name, target: links.append(f"src/{name}") or str(target))
        plans = [plan_of(_source(n, sp, paths.project_yaml, root)) for n, sp in specs.items()]
        writes = ["project.yaml", "cuts.yaml", "cues.yaml", "custom/", *links]
    outputs, built, warns = ingest_media(paths, plans, log_path(root, "new"), dry=True)
    for w in warns:
        r.warn(w)
    src_bytes = sum(p.file.stat().st_size for p in plans)
    r.step(f"{root.name}  ({root})  dry run: nothing written")
    r.info("existing project: project.yaml kept" if existed else f"would write: {', '.join(writes)}")
    for p in plans:
        how = f"  (clean camera on {len(p.camera.trims)} trims)" if p.camera else ""
        r.info(f"source {p.name}: {p.file.name}{how}")
    r.info(
        f"media: {len(built)} to build, {len(outputs) - len(built)} reused"
        + (f": {', '.join(built)}" if built else "")
    )
    r.data = {"dry_run": True, "project": str(root), "created": not existed, "writes": writes,
              "build": built, "reuse": [o.relative_to(paths.media).as_posix() for o in outputs
                                        if o.relative_to(paths.media).as_posix() not in built],
              "source_bytes": src_bytes, "model_calls": 0}  # fmt: skip
    r.next = "rerun without --dry-run"
    return r


def run(ns) -> Report:
    r = Report("new")
    inputs, base = _classify(ns.inputs)
    cfg = _resolve_settings(ns, r)
    slug = ns.slug or base
    parent = _parent(ns)
    root = parent / slug
    if (hit := _in_git_tree(root)) is not None:
        raise VeditError(
            f"{root} is inside a git work tree ({hit}): projects never live in a code repo",
            next="vedit new <input> --dir <folder outside the repo>",
        )
    paths = Paths(root)
    existed = paths.project_yaml.is_file()
    if ns.dry_run:
        return _dry_run(r, root, paths, existed, inputs)
    root.mkdir(parents=True, exist_ok=True)
    paths.src.mkdir(exist_ok=True)
    paths.custom.mkdir(exist_ok=True)
    paths.ensure()

    def link(dst_name: str, target: Path) -> str:
        _link(paths.src / dst_name, target)
        return f"src/{dst_name}"

    sources = _sources(inputs, link)

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
    plans = [plan_of(s) for s in project.sources.values()]
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
        how = f"  (clean camera on {len(p.camera.trims)} trims)" if p.camera else ""
        r.info(f"source {p.name}: {p.file.name}  {d:.1f}s{how}")
    r.info(
        f"media: {len(built)} built, {len(outputs) - len(built)} already done  ({time.monotonic() - t0:.0f}s)"
    )
    r.data = {
        "project": str(root),
        "sources": {n: str(s.origin or s.file) for n, s in project.sources.items()},
        "durations": durations,
        "outputs": [str(o) for o in outputs],
        "built": built,
        "created": not existed,
    }
    r.next = f"cd {root} && vedit transcribe"
    return r
