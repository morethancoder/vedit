"""vedit joins: transcribe the cut program and print only the joins that read wrong. Detached when the Studio
pass is needed (like transcribe); a cached program transcript answers at once."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from vedit import state
from vedit.cut import joins
from vedit.project import Paths, Project, ProjectError, find_project
from vedit.report import Report, VeditError
from vedit.run import log_path
from vedit.words import Edl
from vedit.words import load as load_words

EPILOG = "example: vedit joins --wait"


def add_args(sp) -> None:
    sp.add_argument(
        "--wait", action="store_true", help="work in the foreground (default: detached when Studio is needed)"
    )
    sp.add_argument("--all", action="store_true", help="print every join, not only the mismatches")
    sp.add_argument("--force", action="store_true", help="transcribe the program again even when cached")
    sp.add_argument(
        "--no-confirm",
        action="store_true",
        help="skip the second listen to each flagged join (faster, more false alarms)",
    )
    sp.epilog = EPILOG


def _find(ns) -> tuple[Path, Project]:
    try:
        root = find_project(override=ns.project)
        return root, Project.load(root)
    except ProjectError as e:
        raise VeditError(str(e), next="vedit new <cap-project>  (or: vedit joins --project PATH)") from e


def _spawn(ns, root: Path, paths: Paths) -> int:
    cmd = [sys.executable, "-m", "vedit", "joins", "--wait", "--project", str(root)]
    if ns.force:
        cmd.append("--force")
    log = log_path(root, "joins")
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
    state.start_job(paths, "joins", proc.pid, log, command=" ".join(cmd))
    return proc.pid


def _line(j: dict) -> list[str]:
    src = (
        f"{j['clip']} {j['out']:g}>{j['in']:g}"
        if j["out"] is not None and j["in"] is not None
        else f"{j['clip']} (hold)"
    )
    why = "; ".join(joins.reason(f) for f in j["flags"])
    out = [f"{j['t']:7.2f}  {src}  expected: {j['expected'][0]} ‖ {j['expected'][1]}"]
    out.append(f"{'':7}  {'':{len(src)}}  heard:    {j['heard'][0]} ‖ {j['heard'][1]}")
    if why:
        out.append(f"{'':7}  -> {why}")
    return out


def run(ns) -> Report:
    root, project = _find(ns)
    paths = project.paths
    edl_path, wav = paths.edl / "edl.json", paths.program / "program.wav"
    for f in (edl_path, wav):
        if not f.is_file():
            raise VeditError(f"{f} is not built yet", next="vedit cut")
    key = joins.program_key(project, wav, edl_path)
    r = Report("joins")
    if not ns.wait and (ns.force or joins.cached(paths, key) is None):
        job = state.load(paths)["job"]
        if state.job_state(paths) == "running" and job and job.get("stage") == "joins":
            r.warn(f"a joins job is already running (pid {job.get('pid')}); not starting another")
            r.data = {"started": False, "running": True, "pid": job.get("pid")}
            r.next = "vedit status"
            return r
        pid = _spawn(ns, root, paths)
        r.ok_(f"transcribing the program in the background (pid {pid})")
        r.info(f"log: {log_path(root, 'joins')}")
        r.data = {"started": True, "pid": pid}
        r.next = "vedit status  (then: vedit joins)"
        return r

    child = bool(os.environ.get("VEDIT_JOB")) and ns.wait
    ok = False
    try:
        edl = Edl.load(edl_path)
        words = {c: load_words(paths, c) for c in sorted({p["clip"] for p in edl.pieces})}
        program = joins.program_words(project, edl, key, force=ns.force)
        res = joins.check(edl, words, program)
        if not ns.no_confirm:
            res = joins.confirm(project, edl, words, res)
        ok = True
    finally:
        if child:
            state.finish_job(paths, ok)
    bad = [j for j in res if j["flags"]]
    r.step(f"{project.slug}: {len(res)} joins, {len(bad)} flagged")
    for j in res if ns.all else bad:
        for line in _line(j):
            r.info(line)
    r.ok_(f"{len(res) - len(bad)} joins read as expected") if bad else r.ok_("every join reads as expected")
    r.data = {"joins": len(res), "flagged": len(bad), "results": res if ns.all else bad}
    r.next = (
        "pin or drop a flagged cut in cuts.yaml (vedit guide cuts), then: vedit cut" if bad else "vedit build"
    )
    return r
