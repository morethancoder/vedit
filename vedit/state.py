"""`.vedit/state.json`: the detached job (pid, progress, log) and per-stage input hashes.

Shape: {"job": {pid, stage, command, progress{chunk,chunks,frame,frames}, started, log, status} | null,
        "stages": {stage: {inputs, done, outputs}}}. Writes are atomic (tmp in the same dir, then rename).
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from vedit.project import Paths
from vedit.run import hash_of, sample_hash

STAGES = ("ingest", "transcribe", "cut", "build", "render")
TAIL = 10


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load(paths: Paths) -> dict:
    try:
        data = json.loads(paths.state.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("job", None)
    data.setdefault("stages", {})
    return data


def save(paths: Paths, data: dict) -> None:
    paths.vedit.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=paths.vedit, prefix=".state-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, paths.state)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def start_job(paths: Paths, stage: str, pid: int, log: Path | str, command: str = "", **progress) -> None:
    data = load(paths)
    data["job"] = {
        "pid": pid,
        "stage": stage,
        "command": command,
        "progress": progress,
        "started": _now(),
        "log": str(log),
        "status": "running",
    }
    save(paths, data)


def update_progress(paths: Paths, **progress) -> None:
    data = load(paths)
    if data["job"]:
        data["job"].setdefault("progress", {}).update(progress)
        save(paths, data)


def finish_job(paths: Paths, ok: bool) -> None:
    data = load(paths)
    if data["job"]:
        data["job"]["status"] = "done" if ok else "failed"
        data["job"]["finished"] = _now()
        save(paths, data)


def record_stage(
    paths: Paths, stage: str, inputs_hash: str, outputs: list | None = None, made: str | None = None
) -> None:
    """`inputs` must be what `current_inputs` computes for the stage (or status calls it stale forever);
    `made` is an optional hash of what the stage wrote, which the next stage chains on instead."""
    data = load(paths)
    data["stages"][stage] = {
        "inputs": inputs_hash,
        "done": _now(),
        "outputs": [str(o) for o in outputs or []],
    }
    if made:
        data["stages"][stage]["made"] = made
    save(paths, data)


def pid_alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except (PermissionError, ValueError, TypeError, OverflowError):
        return isinstance(pid, int) and pid > 0  # exists but not ours
    return True


def log_tail(job: dict, n: int = TAIL) -> list[str]:
    try:
        return Path(job["log"]).read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    except (OSError, KeyError, TypeError):
        return []


def job_state(paths: Paths) -> str:
    """running | done | failed | none. A recorded-running job whose pid is gone counts as failed."""
    job = load(paths)["job"]
    if not job:
        return "none"
    if job.get("status") == "running":
        return "running" if pid_alive(job.get("pid")) else "failed"
    return "done" if job.get("status") == "done" else "failed"


# ---- current input hash per stage ----


def _source_hash(s, paths: Paths) -> str | None:
    """Sample hash of a source's media files: the file, or for a Cap source the export and raw camera
    that `vedit new` linked into src/ (`<name>.*`, `<name>-camera.*`). None when one is missing."""
    if s.cap is None:
        return sample_hash(s.path)
    parts = []
    for pat in (f"{s.name}.*", f"{s.name}-camera.*"):
        found = sorted(paths.src.glob(pat))
        if not found:
            return None
        parts += [sample_hash(f) for f in found]
    return None if None in parts else hash_of(parts)


def current_inputs(project, paths: Paths, stages: dict) -> dict[str, str | None]:
    """Hash of what each stage would be made from now; None = a required input file is missing.

    ingest reads the sources (sample hash: size + first and last MiB; hashing GBs each status call is too slow);
    later stages chain on the recorded hash of the stage before, so an upstream redo makes them stale.
    """
    rec = lambda s: (stages.get(s) or {}).get("inputs", "")
    out: dict[str, str | None] = {}
    srcs = [[name, _source_hash(s, paths)] for name, s in sorted(project.sources.items())]
    out["ingest"] = None if any(x[1] is None for x in srcs) else hash_of(srcs)
    out["transcribe"] = hash_of(rec("ingest"), project.lang, project.dialect or "", project.hint or "")
    out["cut"] = hash_of(paths.cuts, rec("transcribe")) if paths.cuts.is_file() else None
    out["build"] = hash_of(paths.cues, rec("cut"), project.style or "") if paths.cues.is_file() else None
    out["render"] = hash_of((stages.get("build") or {}).get("made") or rec("build"))
    return out


def stage_status(project, paths: Paths) -> dict[str, str]:
    stages = load(paths)["stages"]
    cur = current_inputs(project, paths, stages)
    result = {}
    for s in STAGES:
        if cur[s] is None or s not in stages:
            result[s] = "missing"
        else:
            result[s] = "done" if stages[s].get("inputs") == cur[s] else "stale"
    return result


def refuse_while_rendering(paths: Paths, command: str) -> None:
    """The 4K render reads the edl, the 4K program and `.vedit/hf/` while it runs: commands that rewrite them
    must wait for it (a chunk would otherwise mix old and new compositions)."""
    job = load(paths)["job"]
    if job and job.get("stage") == "render" and job_state(paths) == "running":
        from vedit.report import VeditError

        raise VeditError(
            f"a 4K render is running (pid {job.get('pid')}); `vedit {command}` would change files it is reading",
            next="vedit wait  (or `kill <pid>` the render; a rerun resumes)",
            code="busy",
        )
