"""vedit wait: block until the project's detached job (render, cut, transcribe, joins) ends, so an agent never
sleep-polls. Exit 0 when it succeeded, 1 when it failed, 124 on --timeout (the job keeps running)."""

from __future__ import annotations

import json
import sys
import time

from vedit import state
from vedit.project import Project, ProjectError, find_project
from vedit.report import Report, VeditError

EPILOG = "example: vedit wait --timeout 3600 --json   (add --events for NDJSON progress lines on stderr)"
POLL = 2.0


def add_args(sp) -> None:
    sp.add_argument(
        "--timeout", type=float, default=None, metavar="S", help="give up after S seconds (exit 124)"
    )
    sp.add_argument("--events", action="store_true", help="stream progress as NDJSON lines on stderr")
    sp.epilog = EPILOG


def _event(job: dict, js: str) -> dict:
    return {"t": round(time.time(), 1), "stage": job.get("stage"), "state": js, **(job.get("progress") or {})}


def run(ns) -> Report:
    try:
        project = Project.load(find_project(override=ns.project))
    except ProjectError as e:
        raise VeditError(str(e), next="vedit wait --project PATH") from e
    paths = project.paths
    t0 = time.monotonic()
    last = None
    while True:
        job = state.load(paths)["job"] or {}
        js = state.job_state(paths)
        if ns.events and job:
            ev = _event(job, js)
            key = json.dumps({k: v for k, v in ev.items() if k != "t"}, sort_keys=True, default=str)
            if key != last:
                print(json.dumps(ev, ensure_ascii=False, default=str), file=sys.stderr, flush=True)
                last = key
        if js != "running":
            break
        if ns.timeout is not None and time.monotonic() - t0 >= ns.timeout:
            raise VeditError(
                f"the {job.get('stage')} job is still running after {ns.timeout:g}s (pid {job.get('pid')})",
                next="vedit wait  (again; the job keeps running)",
                code="timeout",
            )
        time.sleep(POLL)
    r = Report("wait")
    waited = round(time.monotonic() - t0, 1)
    r.data = {"job": {**job, "state": js} if job else None, "waited_s": waited}
    if js == "none":
        r.info("no job has run in this project")
        r.next = "vedit status"
    elif js == "done":
        r.ok_(f"{job.get('stage')} finished" + (f" (waited {waited:g}s)" if waited else ""))
        r.next = "vedit status"
    else:
        log = job.get("log")
        r.fail(f"{job.get('stage')} failed" + (f"; log: {log}" if log else ""))
        r.next = f"vedit {job.get('stage')}  (reruns resume)"
    return r
