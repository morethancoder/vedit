"""vedit status: each stage done / stale / missing, running job progress, the next command."""

from vedit import channel as chan
from vedit import state
from vedit.graphics import cues as cuesmod
from vedit.graphics import pack as packs
from vedit.project import Project, ProjectError, find_project
from vedit.report import Report, VeditError

NEXT = {
    "ingest": "vedit new",
    "transcribe": "vedit transcribe",
    "cut": "vedit cut",
    "build": "vedit build",
    "render": "vedit render",
}
EPILOG = "example: vedit status --json"


def add_args(sp) -> None:
    sp.epilog = EPILOG


def run(ns) -> Report:
    try:
        root = find_project(override=ns.project)
        project = Project.load(root)
    except ProjectError as e:
        raise VeditError(str(e), next="vedit new <cap-project>  (or: vedit status --project PATH)") from e
    paths = project.paths
    status = state.stage_status(project, paths)
    r = Report("status")
    r.step(f"{project.slug}  ({root})")
    for s in state.STAGES:
        line = f"{s:<11} {status[s]}"
        {"done": r.ok_, "stale": r.warn}.get(status[s], r.info)(line)
    style, origin = chan.style_choice(project, cuesmod.file_style(paths))
    data_style = {"name": style, "from": origin, "found": True}
    try:
        packs.load(style, packs.pack_roots(project.channel))
        r.info(f"style {style} (from {origin})")
    except VeditError as e:
        data_style["found"] = False
        r.fail(f"style {style} (from {origin}) does not resolve: {e.message}")
    job = state.load(paths)["job"]
    js = state.job_state(paths)
    data = {"project": str(root), "stages": status, "style": data_style, "job": None}
    if job and js != "none":
        data["job"] = {**job, "state": js}
        p = job.get("progress") or {}
        bits = [str(p["step"])] if p.get("step") else []
        if p.get("pieces"):
            bits.append(f"piece {p.get('piece', 0)}/{p['pieces']}")
        if p.get("chunks"):
            bits.append(f"chunk {p.get('chunk', 0)}/{p['chunks']}")
        if p.get("frames"):
            bits.append(f"frame {p.get('frame', 0)}/{p['frames']}")
        if p.get("clips"):
            cur = f" ({p['current']})" if p.get("current") else ""
            bits.append(f"clip {p.get('clip', 0)}/{p['clips']}{cur}")
        what = f"{job.get('stage')} (pid {job.get('pid')})"
        if js == "running":
            r.step("running job")
            r.info(f"{what} {', '.join(bits)}".rstrip() + f"  log: {job.get('log')}")
        elif js == "failed":
            tail = state.log_tail(job)
            data["job"]["log_tail"] = tail
            r.step("failed job")
            r.fail(f"{what} died before finishing" + (f" at {', '.join(bits)}" if bits else ""))
            for ln in tail:
                r.info(f"  {ln}")
            r.info(f"  log: {job.get('log')}")
    r.data = data
    first = next((s for s in state.STAGES if status[s] != "done"), None)
    if js == "running":
        r.next = "vedit status  (job still running; do not restart it)"
    elif js == "failed" and job.get("stage") in NEXT:
        r.next = NEXT[job["stage"]] + "  (re-run the failed stage; it resumes)"
    elif first:
        r.next = NEXT[first]
    return r
