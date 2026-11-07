"""vedit render: the 4K60 master, detached, chunked, resumable (vedit/render/master.py does the work)."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

from vedit import state
from vedit.project import Project, ProjectError, find_project
from vedit.render import master
from vedit.report import Report, VeditError
from vedit.run import log_path

EPILOG = "example: vedit render            (detached; follow with `vedit status`)"


def add_args(sp) -> None:
    sp.add_argument("--wait", action="store_true", help="work in the foreground (default: detached)")
    sp.add_argument(
        "--output",
        action="append",
        metavar="ID",
        help="render this output (repeat; `all`); default: the 4K film",
    )
    sp.epilog = EPILOG


def _find(ns) -> tuple[Path, Project]:
    try:
        root = find_project(override=ns.project)
        return root, Project.load(root)
    except ProjectError as e:
        raise VeditError(str(e), next="vedit render --project PATH") from e


def _spawn(root: Path, paths, outputs: list[str] | None = None) -> int:
    cmd = [sys.executable, "-m", "vedit", "render", "--wait", "--project", str(root)]
    for o in outputs or []:
        cmd += ["--output", o]
    log = log_path(root, "render")
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "ab") as out:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=out,
            start_new_session=True,  # survives the calling shell/agent ending
            env={**os.environ, "VEDIT_JOB": "1"},
        )
    state.start_job(paths, "render", proc.pid, log, command=" ".join(cmd), step="start")
    return proc.pid


def _run_outputs(ns, root: Path, project, r: Report, child: bool) -> Report:
    """Final renders of non-16:9 outputs (1080-wide, 60 fps): detached like the master unless --wait."""
    from vedit.commands.draft import pick_outputs, run_outputs

    paths = project.paths
    outs = pick_outputs(project, ns.output)
    if getattr(ns, "dry_run", False):
        r.ok_(f"dry run: would render {', '.join(o.id for o in outs)} at 60 fps")
        r.data = {"dry_run": True, "outputs": [o.id for o in outs]}
        return r
    if not ns.wait:
        pid = _spawn(root, paths, [o.id for o in outs])
        r.ok_(f"rendering {', '.join(o.id for o in outs)} in the background (pid {pid})")
        r.data = {"started": True, "pid": pid, "outputs": [o.id for o in outs]}
        r.next = "vedit wait"
        return r
    ok = False
    try:
        res = run_outputs(ns, project, final=True)
        ok = True
    finally:
        if child:
            state.finish_job(paths, ok)
    return res


def _stop(paths) -> None:
    """`kill <pid>` of the job: stop the HyperFrames group, mark the job failed, then end this whole process
    group at once (a thread pool of ffmpeg pieces would otherwise finish its queue first). Finished pieces,
    cut-outs and chunks are kept; a rerun resumes."""
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    try:
        master.kill_stale(state.load(paths)["job"])
        state.finish_job(paths, False)
        os.killpg(os.getpgrp(), signal.SIGTERM)  # the `timeout` wrappers stop their whole ffmpeg/Chrome trees
        time.sleep(4)
    finally:
        os.killpg(os.getpgrp(), signal.SIGKILL)


def _plan(paths) -> tuple[int, int, float, bool]:
    ch = master.load_chunks(paths)
    lay = master.layout(paths)
    n = len(ch["bounds"]) - 1
    done = sum(1 for i in range(n) if (lay["chunks"] / f"chunk-{i:02d}.key").is_file())
    return n, done, ch["total"], (paths.program / "master.mp4").is_file()


def run(ns) -> Report:
    root, project = _find(ns)
    paths = project.paths
    r = Report("render")
    child = bool(os.environ.get("VEDIT_JOB"))
    if not child and state.job_state(paths) == "running":
        job = state.load(paths)["job"]
        raise VeditError(
            f"a {job.get('stage')} job is already running (pid {job.get('pid')})",
            next="vedit wait  (do not restart it)",
            code="busy",
        )
    if not child:
        killed = master.kill_stale(state.load(paths)["job"])
        if killed:
            r.warn("stopped a HyperFrames render left over from a job that died")
    if getattr(ns, "output", None):
        return _run_outputs(ns, root, project, r, child)
    n, done, total, have_prog = _plan(paths)
    need = master.disk_need(total, done, n, have_prog)
    if getattr(ns, "dry_run", False):
        free = shutil.disk_usage(paths.vedit).free
        r.step(f"{project.slug}  ({root})")
        r.info(f"would render {n - done} of {n} chunks at 4K60 ({done} kept from an earlier run)")
        r.info(f"4K program: {'kept' if have_prog else 'would be rendered first'}; film {total:.1f}s")
        (r.info if free >= need * 1.1 else r.warn)(
            f"disk: {free / 1e9:.0f} GB free, needs ~{need / 1e9:.0f} GB"
        )
        r.ok_("dry run: nothing started")
        r.data = {"dry_run": True, "chunks": n, "to_render": n - done, "reused": done, "seconds": round(total, 2),
                  "program_ready": have_prog, "need_gb": round(need / 1e9, 1), "free_gb": round(free / 1e9, 1)}  # fmt: skip
        r.next = "vedit render"
        return r
    free = master.check_disk(paths, need)
    if not ns.wait:
        pid = _spawn(root, paths)
        r.step(f"{project.slug}  ({root})")
        r.ok_(
            f"rendering the 4K60 master in the background (pid {pid}): {n} chunks, {done} from an earlier run (kept if unchanged)"
        )
        r.info(f"disk: {free / 1e9:.0f} GB free, needs ~{need / 1e9:.0f} GB")
        r.info(f"log: {log_path(root, 'render')}")
        r.data = {"started": True, "pid": pid, "chunks": n, "done": done, "need_gb": round(need / 1e9, 1)}
        r.next = "vedit status"
        return r

    log = log_path(root, "render")
    inputs = state.current_inputs(project, paths, state.load(paths)["stages"])["render"]  # before: a rebuild
    progress = (lambda **p: state.update_progress(paths, **p)) if child else (lambda **p: None)
    if child:
        signal.signal(signal.SIGTERM, lambda *_: _stop(paths))
    ok = False
    try:
        res = master.render(project, paths, progress, log)
        state.record_stage(paths, "render", inputs or "", [res["master"]])
        r.artifact(res["master"], "video")
        ok = True
    finally:
        if child:
            state.finish_job(paths, ok)
    s = res["seconds"]
    v = res["verify"]
    r.step(f"{project.slug}  ({root})")
    r.ok_(
        f"master {res['master']}  ({v['size']} {v['fps']}, {v['frames']} frames = {v['want_frames']} wanted)"
    )
    r.info(
        f"4K program {s['program']:.0f}s, cut-outs {s['cutouts']:.0f}s, "
        f"{len(s['chunks'])} chunks rendered ({res['reused']} reused) {sum(s['chunks']):.0f}s, join {s['join']:.0f}s"
    )
    r.data = res
    r.next = "vedit clean  (caches; `--posted` only after the upload)"
    return r
