"""vedit cut: cuts.yaml -> resolve -> [listen/refine] -> edl -> [render]. Detached by default, like transcribe."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

from vedit import state
from vedit.commands.transcribe import _write
from vedit.cut import cutsfile, edl, program, signal
from vedit.project import Paths, Project, ProjectError, find_project
from vedit.report import Report, VeditError
from vedit.run import log_path, sample_hash
from vedit.words import load as load_words

EPILOG = "example: vedit cut --wait --edl-only"
FIXES = "edit cuts.yaml (vedit guide cuts), then: vedit cut"


def add_args(sp) -> None:
    sp.add_argument("--wait", action="store_true", help="work in the foreground (default: detached)")
    sp.add_argument(
        "--edl-only", action="store_true", help="stop after the edl (.vedit/edl/edl.json); renders nothing"
    )
    sp.add_argument(
        "--no-listen",
        action="store_true",
        help="skip listening for exact boundaries: snap to the quietest point",
    )
    sp.add_argument(
        "--master",
        action="store_true",
        help="also render the 4K60 master (.vedit/program/master.mp4) after the 1080p30 proxy",
    )
    sp.epilog = EPILOG


def _find(ns) -> tuple[Path, Project]:
    try:
        root = find_project(override=ns.project)
        return root, Project.load(root)
    except ProjectError as e:
        raise VeditError(str(e), next="vedit new <video>  (or: vedit cut --project PATH)") from e


def _spawn(ns, root: Path, paths: Paths) -> int:
    cmd = [sys.executable, "-m", "vedit", "cut", "--wait", "--project", str(root)]
    for flag, on in (("--edl-only", ns.edl_only), ("--no-listen", ns.no_listen), ("--master", ns.master)):
        if on:
            cmd.append(flag)
    log = log_path(root, "cut")
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "ab") as out:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=out,
            start_new_session=True,
            env={**os.environ, "VEDIT_JOB": "1"},
        )
    state.start_job(paths, "cut", proc.pid, log, command=" ".join(cmd), step="resolve")
    return proc.pid


def mmss(t: float) -> str:
    return f"{int(t // 60):02d}:{t % 60:05.2f}"


def _wavs(project: Project, paths: Paths) -> dict[str, Path]:
    out = {}
    for n in sorted(project.sources):
        wav = paths.media / f"{n}-48k.wav"
        if not wav.is_file():
            raise VeditError(f"missing {wav}", next="vedit new <input>  (rebuilds media)")
        out[n] = wav
    return out


def get_envelope(paths: Paths, clip: str, wav: Path) -> np.ndarray:
    """Envelope cached at edl/envelope-<clip>.npy, keyed by the WAV's sample hash (recorded in the .key file)."""
    npy, key = paths.edl / f"envelope-{clip}.npy", paths.edl / f"envelope-{clip}.key"
    ident = sample_hash(wav) or ""
    if npy.is_file() and key.is_file() and key.read_text() == ident:
        return np.load(npy)
    paths.edl.mkdir(parents=True, exist_ok=True)
    db = signal.envelope(wav)
    np.save(npy, db)
    key.write_text(ident)
    return db


def _problem_lines(problems: list[dict]) -> list[str]:
    out = []
    for p in problems:
        out.append(f"{p['section']}[{p['cut']}] near {p['near']} '{p['text']}': {p['error']}")
    return out


def _listen_hook(paths, cuts, words, log, progress):
    """Refine hook: vedit.cut.refine.run(project, paths, cuts, words_by_clip, log, progress) -> refined dict."""
    if importlib.util.find_spec("vedit.cut.refine") is None:
        return None
    return importlib.import_module("vedit.cut.refine").run


def _dry_run(ns, project: Project, paths: Paths, r: Report) -> Report:
    """What `vedit cut` would listen to, write and render, writing nothing (no job is started)."""
    if not paths.cuts.is_file():
        raise VeditError(f"no cuts file at {paths.cuts}", next="write cuts.yaml (vedit guide cuts)")
    r.step(f"{project.slug}  ({paths.root})  dry run: nothing written")
    wavs = _wavs(project, paths)
    cf = cutsfile.load(paths.cuts)
    words = {n: load_words(paths, n) for n in wavs}
    durations = {n: sf.info(str(w)).duration for n, w in wavs.items()}
    cuts, problems = cutsfile.resolve(cf, words, durations)
    if problems:
        lines = _problem_lines(problems)
        raise VeditError(f"{len(lines)} cut(s) did not resolve:\n  " + "\n  ".join(lines), next=FIXES)
    refined: dict = {}
    to_listen = 0
    if importlib.util.find_spec("vedit.cut.refine"):
        from vedit.cut import refine

        refined = refine.cached(paths, cuts, words)
        if not ns.no_listen:
            to_listen = sum(1 for c in cuts if c.kind in ("phrase", "filler") and c.pin is None) - len(
                refined
            )
    envs = {}
    for n, w in wavs.items():  # the cached envelope when valid, else computed in memory (not saved)
        npy, key = paths.edl / f"envelope-{n}.npy", paths.edl / f"envelope-{n}.key"
        ok = npy.is_file() and key.is_file() and key.read_text() == (sample_hash(w) or "")
        envs[n] = np.load(npy) if ok else signal.envelope(w)
    zoom = {n for n, s in project.sources.items() if s.punch_in}
    data, info = edl.build(cuts, refined, envs, words, durations, cf.pauses, edl.chapter_holds(cf.chapters),
                           cf.end, zoom)  # fmt: skip
    approx = f" (approximate: {to_listen} boundaries still to listen to)" if to_listen else ""
    r.ok_(f"program {mmss(data['total'])}, {info['pieces']} pieces, {len(cuts)} cuts{approx}")
    r.info(
        f"listen: {to_listen} cut(s) through Studio, {len(refined)} cached"
        if not ns.no_listen
        else "listen: off"
    )
    writes = [str(paths.edl / "cuts.json"), str(paths.edl / "edl.json")]
    renders = {}
    if not ns.edl_only:
        for profile in ("proxy", "master") if ns.master else ("proxy",):
            items = program.plan(data, paths, profile)
            files = {d for _, _, d in items}
            missing = sum(1 for d in files if not d.is_file())
            renders[profile] = {"pieces": len(files), "to_render": missing, "reused": len(files) - missing}
            r.info(f"render {profile}: {missing} piece(s) to render, {len(files) - missing} reused")
            writes.append(str(paths.program / program.PROFILES[profile]["out"]))
    r.data = {"dry_run": True, "total": data["total"], "pieces": info["pieces"], "cuts": len(cuts),
              "to_listen": to_listen, "listen_cached": len(refined), "renders": renders, "writes": writes,
              "model_calls": {"studio_listen_cuts": to_listen}}  # fmt: skip
    r.next = "vedit cut  (without --dry-run)"
    return r


def run(ns) -> Report:
    root, project = _find(ns)
    paths = project.paths
    r = Report("cut")
    if ns.dry_run:  # writes nothing, so it is safe while a render runs
        return _dry_run(ns, project, paths, r)
    if not os.environ.get("VEDIT_JOB"):
        state.refuse_while_rendering(paths, "cut")
    job = state.load(paths)["job"]
    if not ns.wait:
        if state.job_state(paths) == "running" and job and job.get("stage") == "cut":
            r.warn(f"a cut job is already running (pid {job.get('pid')}); not starting another")
            r.data = {"started": False, "running": True, "pid": job.get("pid")}
            r.next = "vedit status"
            return r
        if not paths.cuts.is_file():
            raise VeditError(f"no cuts file at {paths.cuts}", next="write cuts.yaml (vedit guide cuts)")
        pid = _spawn(ns, root, paths)
        r.step(f"{project.slug}  ({root})")
        r.ok_(f"cutting in the background (pid {pid})")
        r.info(f"log: {log_path(root, 'cut')}")
        r.data = {"started": True, "pid": pid}
        r.next = "vedit status"
        return r

    child = bool(os.environ.get("VEDIT_JOB"))
    ok = False
    try:
        _run(ns, project, paths, r, child)
        ok = True
    finally:
        if child:
            state.finish_job(paths, ok)
    return r


def _run(ns, project: Project, paths: Paths, r: Report, child: bool) -> None:
    step = (lambda s: state.update_progress(paths, step=s)) if child else (lambda s: None)
    r.step(f"{project.slug}  ({paths.root})")
    log = log_path(paths.root, "cut")
    wavs = _wavs(project, paths)
    # 1. resolve
    step("resolve")
    cf = cutsfile.load(paths.cuts)
    words = {n: load_words(paths, n) for n in wavs}
    durations = {n: sf.info(str(w)).duration for n, w in wavs.items()}
    cuts, problems = cutsfile.resolve(cf, words, durations)
    paths.edl.mkdir(parents=True, exist_ok=True)
    _write(
        paths.edl / "cuts.json",
        json.dumps(
            {
                "cuts": [{**c.__dict__, "key": c.key} for c in cuts],
                "problems": problems,
            },
            ensure_ascii=False,
            indent=1,
        ),
    )
    if problems:
        lines = _problem_lines(problems)
        raise VeditError(f"{len(lines)} cut(s) did not resolve:\n  " + "\n  ".join(lines), next=FIXES)
    # 2. refine hook (listen for exact boundaries)
    step("refine")
    refined: dict = {}
    hook = None if ns.no_listen else _listen_hook(paths, cuts, words, log, step)
    if hook is not None:

        def note(line: str) -> None:
            log.parent.mkdir(parents=True, exist_ok=True)
            with log.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

        def listened(done: int, total: int) -> None:
            if child:
                state.update_progress(paths, step="refine", piece=done, pieces=total)

        refined = hook(project, paths, cuts, words, note, listened)
    elif importlib.util.find_spec("vedit.cut.refine"):  # cached listens still apply without listening
        from vedit.cut import refine

        refined = refine.cached(paths, cuts, words)
    # 3. edl
    step("edl")
    envs = {n: get_envelope(paths, n, w) for n, w in wavs.items()}
    zoom = {n for n, s in project.sources.items() if s.punch_in}
    data, info = edl.build(
        cuts,
        refined,
        envs,
        words,
        durations,
        cf.pauses,
        edl.chapter_holds(cf.chapters),
        cf.end,
        zoom,
    )
    _write(paths.edl / "edl.json", json.dumps(data, indent=0))
    # 4. report the edl, then render (skipped with --edl-only)
    kinds = ", ".join(f"{k} {v}" for k, v in sorted(info["cuts"].items())) or "none"
    r.ok_(f"program {mmss(data['total'])}, {info['pieces']} pieces, {info['holds']} chapter holds")
    r.ok_(f"cuts applied: {kinds}; pauses shortened {info['pauses']}; pins applied {info['pins']}")
    if info["zoomed"]:
        r.info(f"{info['zoomed']} piece(s) punch in {edl.ZOOM}x")
    for n in info["notes"]:
        r.warn(n)
    outputs = [paths.edl / "edl.json", paths.edl / "cuts.json"]
    renders = []
    if not ns.edl_only:
        for profile in ("proxy", "master") if ns.master else ("proxy",):
            label = f"render {profile}"
            step(label)
            prog = (
                (lambda d, n, lb=label: state.update_progress(paths, step=f"{lb} {d}/{n}")) if child else None
            )
            res = program.render(data, paths, profile, prog, log)
            renders.append(res)
            outputs.append(Path(res["path"]))
            r.ok_(
                f"{profile}: {res['rendered']} piece(s) rendered, {res['reused']} reused, {res['seconds']}s; "
                f"{res['frames']} frames, audio {res['audio_s']}s, program {mmss(res['total'])} -> {res['path']}"
            )
            if not res["ok"]:
                r.warn(f"{profile}: expected {res['want_frames']} frames and {res['total']:.2f}s of audio")
        outputs.append(paths.program / "program.wav")
    state.record_stage(
        paths,
        "cut",
        state.current_inputs(project, paths, state.load(paths)["stages"])["cut"] or "",
        outputs,
    )
    r.data = {
        "total": data["total"],
        "fade_start": data["fade_start"],
        **info,
        "problems": [],
        "renders": renders,
    }
    r.artifact(paths.edl / "edl.json", "edl")
    for res in renders:
        r.artifact(res["path"], "video")
    r.next = "vedit joins" if renders else "vedit cut  (without --edl-only, to render the program)"
