"""vedit build: cues.yaml + style pack -> layout plan -> `.vedit/hf/` HyperFrames project, linted and checked."""

from __future__ import annotations

import json
import time
from pathlib import Path

from vedit import channel as chan
from vedit import state
from vedit.cut import cutsfile
from vedit.graphics import compose, cutouts, pages, place
from vedit.graphics import cues as cuesmod
from vedit.graphics import pack as packs
from vedit.graphics.faces import FaceTrack
from vedit.graphics.plan import build_plan
from vedit.project import Project, ProjectError, find_project
from vedit.report import Report, VeditError
from vedit.run import hash_of, log_path
from vedit.run import run as sh
from vedit.versions import HYPERFRAMES
from vedit.words import Edl
from vedit.words import load as load_words

EPILOG = "example: vedit build --plan"
LINT_TIMEOUT, CHECK_TIMEOUT = 300, 900


def add_args(sp) -> None:
    sp.add_argument("--plan", action="store_true", help="print the layout plan only; writes nothing")
    sp.add_argument("--no-check", action="store_true", help="skip `hyperframes lint` + `check` (faster loop)")
    sp.add_argument("--output", action="append", metavar="ID", help="build only these outputs (default: all)")
    sp.epilog = EPILOG


def mmss(t: float) -> str:
    return f"{int(t // 60):02d}:{t % 60:05.2f}"


def _load(ns):
    try:
        root = find_project(override=ns.project)
        project = Project.load(root)
    except ProjectError as e:
        raise VeditError(str(e), next="vedit new <cap-project>  (or: vedit build --project PATH)") from e
    paths = project.paths
    state.refuse_while_rendering(paths, "build")
    edl_f = paths.edl / "edl.json"
    if not edl_f.is_file():
        raise VeditError(f"{edl_f} is not built yet", next="vedit cut")
    if not (paths.program / "proxy.mp4").is_file():
        raise VeditError(f"{paths.program / 'proxy.mp4'} is missing", next="vedit cut")
    return project, paths, Edl.load(edl_f)


def checked_pack(name: str, roots: list | None = None) -> packs.Pack:
    """The pack, or one error listing every problem it has (pack.check)."""
    pk = packs.load(name, roots)
    probs = packs.check(pk)
    if probs:
        raise VeditError(
            f"style {name!r} has {len(probs)} problem(s):\n  " + "\n  ".join(probs),
            next="fix the pack (vedit guide styles), then: vedit styles",
        )
    return pk


def make_plan(project, paths, edl):
    clips = list(project.sources)
    words = {c: load_words(paths, c) for c in clips}
    roots = packs.pack_roots(project.channel)  # channel packs, then global, then built-in
    style = chan.style_choice(project, cuesmod.file_style(paths))[0]
    pool: dict[str, packs.Pack] = {}

    def pack_of(name: str) -> packs.Pack:
        if name not in pool:
            pool[name] = checked_pack(name, roots)
        return pool[name]

    main = pack_of(style)  # checked before the cues, so a broken pack shows all its problems at once
    cues = cuesmod.load(project, paths, edl, words, roots)
    clogos = cuesmod.custom_logos(paths)
    logos = {**main.logos(), **clogos}
    chs = cuesmod.chapters(cutsfile.load(paths.cuts), edl, main, logos, style) if paths.cuts.exists() else []
    track = FaceTrack.load(paths, clips, edl)
    lum = place.Lum(paths.program / "proxy.mp4", paths.vedit / "build" / "lum.json")
    plan = build_plan(cues + chs, edl, track, lum, main.advances(), main.data.get("big"))
    lum.save()
    env = pages.Env(
        paths, project.lang, chan.effective_accent(project)[0], project.plug, project.slug, clogos
    )
    return plan, main, (lambda cue: pack_of(cue.style)), env


def build_outputs(project, paths, edl, plan, main, pack_for, env, mattes, only=None) -> list:
    """Each non-16:9 output's HyperFrames project under `.vedit/out/<id>/hf/` (vedit.formats.compose_out)."""
    from vedit.commands import reframe as rfcmd
    from vedit.formats import compose_out
    from vedit.formats import layout as lay
    from vedit.outputs import words_by_clip

    listed = {o.id for o in project.outputs}
    for d in (Path(paths.vedit) / "out").glob("*"):  # an output removed from project.yaml
        if d.is_dir() and d.name not in listed:
            import shutil

            shutil.rmtree(d, ignore_errors=True)
    outs = [o for o in project.outputs if o.aspect != "16:9" and (not only or o.id in only)]
    if not outs:
        return []
    track = FaceTrack.load(paths, list(project.sources), edl)
    wbc = words_by_clip(project) if any(o.range for o in outs) else None
    pw = paths.program / "P.words.json"
    words = json.loads(pw.read_text(encoding="utf-8")) if pw.is_file() else None
    res = []
    for o in outs:
        pts, info = rfcmd.crop_path(project, o, edl, track, wbc)
        geo = lay.geometry(o, points=pts, t0=info["t0"], t1=info["t1"])
        res.append(compose_out.write(paths, o, geo, plan, pack_for, main, edl, env, track, mattes, words))
    return res


def hf_cmd(sub: str, hf: Path, *extra: str) -> list[str]:
    return ["npx", "--yes", f"hyperframes@{HYPERFRAMES}", sub, str(hf), *extra]


def _json(text: str):
    start = min((i for i in (text.find("{"), text.find("[")) if i >= 0), default=-1)
    try:
        return json.loads(text[start:]) if start >= 0 else None
    except ValueError:
        return None


# warnings that are true of every generated project by design
BENIGN = {
    "composition_file_too_large",  # index.html holds every host, sound and zoom of the film
    "nested_media_start_basis_ambiguous",  # plug demo starts 0.6 s into its graphic (local time, as meant)
}


def findings(data: dict):
    """(section, finding) from lint JSON (top-level `findings`) or check JSON (one block per audit)."""
    for f in data.get("findings") or []:
        yield "lint", f
    for sec in ("lint", "runtime", "layout", "motion", "contrast"):
        block = data.get(sec)
        if isinstance(block, dict):
            for f in block.get("findings") or []:
                yield sec, f


def checks(hf: Path, log: Path) -> tuple[list[str], list[str], dict]:
    """(errors, warnings, numbers) from `hyperframes lint` then `check` (time-boxed, stdin closed)."""
    errs, warns, nums = [], [], {}
    for sub, limit in (("lint", LINT_TIMEOUT), ("check", CHECK_TIMEOUT)):
        proc = sh(hf_cmd(sub, hf, "--json"), limit, cwd=hf, log=log, check=False)
        data = _json(proc.stdout or "")
        if data is None:
            tail = ((proc.stderr or "") + (proc.stdout or "")).strip().splitlines()[-6:]
            errs.append(f"hyperframes {sub}: exit {proc.returncode}, no JSON: " + " | ".join(tail))
            break
        for sec, f in findings(data):
            code = f.get("code") or f.get("rule") or ""
            if code in BENIGN:
                continue
            where = Path(str(f.get("file") or f.get("sourceFile") or "")).name or f.get("selector") or ""
            line = f"{sec}: {code} {f.get('message') or ''}".strip() + (f" ({where})" if where else "")
            bucket = errs if str(f.get("severity", "")).lower() == "error" else warns
            if str(f.get("severity", "")).lower() in ("error", "warning") and line not in bucket:
                bucket.append(line)
        nums[sub] = {"exit": proc.returncode, "ok": data.get("ok", proc.returncode == 0)}
        if sub == "check":  # a lint error turns these audits off, so 0 samples means nothing ran
            nums[sub]["layout_samples"] = len((data.get("layout") or {}).get("samples") or [])
            c = data.get("contrast") or {}
            nums[sub]["contrast"] = f"{c.get('passed', 0)}/{c.get('checked', 0)}"
        if proc.returncode != 0 and not any(e.startswith(sub) for e in errs):
            errs.append(f"hyperframes {sub} failed (exit {proc.returncode}); see {log}")
        if errs:
            break  # a lint error switches check's audits off: fix lint first
    return errs, warns, nums


def run(ns) -> Report:
    t0 = time.monotonic()
    project, paths, edl = _load(ns)
    plan, main, pack_for, env = make_plan(project, paths, edl)
    r = Report("build")
    probs = plan.problems()
    on = sum(1 for z in plan.zooms if z[1] != 1.0)
    data = {"graphics": len(plan.items), "zooms": on, "focus": len(plan.focus), "problems": probs}
    if ns.plan:
        r.step(f"plan: {len(plan.items)} graphics, {on} punch-ins, {len(plan.focus)} blur windows")
        for p in plan.items:
            r.info(f"{mmss(p.start)} {p.dur:5.1f}s  {p.id:18s} {p.note()}")
        for x in probs:
            r.warn(x)
        data["items"] = [
            {
                "id": p.id,
                "type": p.cue.type,
                "start": round(p.start, 3),
                "dur": round(p.dur, 3),
                "note": p.note(),
            }
            for p in plan.items
        ]
        r.data, r.next = data, "vedit build"
        return r
    for p in plan.items:
        if p.notes:
            r.info(f"{mmss(p.start)} {p.id}: " + "; ".join(p.notes))
    for x in probs:
        r.warn(x)
    ranges = {f"mt-{p.id}": (p.start, p.dur) for p in plan.items if p.cue.type == "big-number"}
    log = log_path(paths.root, "build")
    mattes = cutouts.ensure(project, paths, ranges, variant="proxy", log=log)
    res = compose.write(paths, plan, pack_for, main, edl, env, mattes)
    r.ok_(
        f"{len(res.graphics)} graphics ({len(res.written)} written, {len(res.reused)} unchanged"
        + (f", {len(res.removed)} removed" if res.removed else "")
        + f"), {len(res.sfx)} sounds, {on} punch-ins, {len(plan.focus)} blur windows, "
        f"{len(res.chunks) - 1} render chunks"
    )
    if ranges:
        r.info(f"cut-outs: {len(mattes.rebuilt)} rebuilt, {len(mattes.reused)} reused")
    outs = build_outputs(project, paths, edl, plan, main, pack_for, env, mattes, ns.output)
    for o in outs:
        r.ok_(f"output {o.oid}: {len(o.graphics)} graphics over {o.t0:.1f}-{o.t1:.1f}s "
              f"({len(o.written)} written, {len(o.reused)} unchanged)"
              + (f", captions pause {len(o.pauses)}x" if o.pauses else "")
              + ("" if o.captioned or not o.wants_captions else "; no captions: run `vedit joins` first"))  # fmt: skip
        r.artifact(o.hf / "index.html", "composition")
    data.update(
        sounds=len(res.sfx),
        written=res.written,
        removed=res.removed,
        reused=len(res.reused),
        cutouts={"rebuilt": mattes.rebuilt, "reused": mattes.reused},
        chunks=res.chunks,
        hf=str(paths.hf),
    )
    data["outputs"] = [{"id": o.oid, "hf": str(o.hf), "graphics": len(o.graphics), "span": [o.t0, o.t1],
                        "pauses": o.pauses} for o in outs]  # fmt: skip
    if not ns.no_check:
        for o in outs:
            oe, ow, _ = checks(o.hf, log)
            for w in ow:
                r.warn(f"{o.oid}: {w}")
            for e in oe:
                r.fail(f"{o.oid}: {e}")
        errs, warns, nums = checks(Path(paths.hf), log)
        data["check"] = {"errors": errs, "warnings": warns, **nums}
        for w in warns:
            r.warn(w)
        for e in errs:
            r.fail(e)
        if not errs:
            c = nums.get("check", {})
            r.ok_(
                f"hyperframes lint + check passed: {c.get('layout_samples', 0)} layout samples, "
                f"contrast {c.get('contrast', '0/0')}" + (f", {len(warns)} warnings" if warns else "")
            )
    data["seconds"] = round(time.monotonic() - t0, 1)
    if r.ok:
        manifest = json.loads((Path(paths.hf) / "manifest.json").read_text())
        key = hash_of(manifest, (Path(paths.hf) / "index.html").read_text())
        cur = state.current_inputs(project, paths, state.load(paths)["stages"])["build"]
        state.record_stage(paths, "build", cur or "", [Path(paths.hf) / "index.html"], made=key)
    r.artifact(Path(paths.hf) / "index.html", "composition")
    r.data = data
    r.next = "vedit review" if r.ok else "fix the problems above (vedit guide cues), then: vedit build"
    return r
