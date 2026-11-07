"""vedit output: list, add or remove what the project produces (the YouTube master, clips, shorts, stories,
feed posts). Each output has its own aspect, platforms and captions; all share the project's cut."""

from __future__ import annotations

import argparse

from vedit import formats as fm
from vedit import outputs as om
from vedit.project import Output, Project, ProjectError, find_project, parse_outputs
from vedit.report import Report, VeditError

EPILOG = 'example: vedit output add reel-1 --from "first words" --to "last words" --near "A 245"'


def add_args(sp) -> None:
    sp.add_argument("action", choices=["list", "add", "rm"], metavar="list|add|rm", help=argparse.SUPPRESS)
    sp.add_argument("id", nargs="?", help=argparse.SUPPRESS)
    sp.add_argument("--kind", choices=["master", "clip", "short", "story", "post"], metavar="K",
                    help="master|clip|short|story|post (default clip)")  # fmt: skip
    sp.add_argument("--aspect", metavar="W:H", help="16:9 9:16 4:5 1:1 3:4 2:3")
    sp.add_argument("--platforms", metavar="P,P", help="e.g. instagram-reels,tiktok")
    sp.add_argument("--from", dest="from_", metavar="WORDS", help="clip: first words")
    sp.add_argument("--to", metavar="WORDS", help="clip: last words")
    sp.add_argument("--near", metavar="AT", help="clip: where `from` is said ('A 245')")
    sp.add_argument("--captions", choices=["burned", "srt", "none"], metavar="C", help="burned|srt|none")
    sp.epilog = EPILOG


def _load(ns) -> Project:
    try:
        return Project.load(find_project(override=ns.project))
    except ProjectError as e:
        raise VeditError(str(e), next="vedit new <recording>", code="bad_input") from e


def _row(project: Project, o: Output, wbc) -> dict:
    d = o.as_dict()
    size = fm.canvas(o.aspect)
    d["canvas"] = list(size)
    d["safe_box"] = fm.safe_box(o.platforms, size).as_dict()
    if o.range and wbc is not None:
        try:
            rng = om.resolve_range(project, o, wbc)
            d["resolved"] = {**rng.as_dict(), "seconds": round(rng.t1 - rng.t0, 2)}
        except VeditError as e:
            d["resolved"] = {"error": e.message}
    return d


def run(ns) -> Report:
    project = _load(ns)
    r = Report("output")
    f = project.paths.project_yaml
    outs = list(project.outputs)
    if ns.action in ("add", "rm") and not ns.id:
        raise VeditError(f"vedit output {ns.action} needs an id", next="vedit output --help", code="usage")
    if ns.action == "rm":
        if ns.id not in {o.id for o in outs}:
            raise VeditError(f"no output called {ns.id!r}", next="vedit output list", code="bad_input")
        outs = [o for o in outs if o.id != ns.id]
        if not outs:
            raise VeditError(
                "a project needs at least one output", next="vedit output list", code="bad_input"
            )
        om.write(f, outs)
        r.ok_(f"removed output {ns.id}")
    elif ns.action == "add":
        if ns.id in {o.id for o in outs}:
            raise VeditError(f"output {ns.id!r} exists", next=f"vedit output rm {ns.id}", code="bad_input")
        spec: dict = {"id": ns.id, "kind": ns.kind or "clip"}
        if ns.aspect:
            spec["aspect"] = ns.aspect
        if ns.platforms:
            spec["platforms"] = [p.strip() for p in ns.platforms.split(",") if p.strip()]
        if ns.from_ or ns.to or ns.near:
            spec["range"] = {k: v for k, v in (("from", ns.from_), ("to", ns.to), ("near", ns.near)) if v}
        if ns.captions:
            spec["captions"] = ns.captions
        try:
            (new,) = parse_outputs([spec], f)
        except ProjectError as e:
            raise VeditError(str(e).replace(f"{f}: outputs[0]", f"output {ns.id}"), code="bad_input") from e
        if new.range:
            rng = om.resolve_range(project, new)  # the words must be found before it is saved
            r.info(f"{new.id}: {rng.clip} {rng.t0:.1f}-{rng.t1:.1f} ({rng.t1 - rng.t0:.1f}s of source)")
        outs.append(new)
        om.write(f, outs)
        r.ok_(f"added output {new.id} ({new.kind}, {new.aspect}, {', '.join(new.platforms)})")
    try:
        wbc = om.words_by_clip(project)
    except VeditError:
        wbc = None
    rows = [_row(project, o, wbc) for o in outs]
    if ns.action == "list":
        for d in rows:
            sb = d["safe_box"]
            extra = ""
            if "resolved" in d:
                res = d["resolved"]
                extra = (
                    f"  ! {res['error']}"
                    if "error" in res
                    else f"  {res['clip']} {res['t0']:.1f}-{res['t1']:.1f}"
                )
            r.info(f"{d['id']:<14} {d['kind']:<6} {d['aspect']:<5} {','.join(d['platforms'])}  "
                   f"captions {d['captions']}  text box {sb['w']:.0f}x{sb['h']:.0f}{extra}")  # fmt: skip
    r.data = {"outputs": rows, "explicit": om.explicit(f)}
    r.next = "vedit formats  (platform safe zones)" if ns.action == "list" else "vedit output list"
    return r
