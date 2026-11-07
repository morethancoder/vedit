"""vedit doctor: tools, pinned HyperFrames, Studio, Ollama, free disk. Works with or without a project."""

import shutil
from pathlib import Path

from vedit import state, versions
from vedit.project import Project, ProjectError, find_project
from vedit.report import Report, VeditError
from vedit.run import run as sh

# Rough free space each stage needs, GB (render: 4K60 chunks + joined master + cut-out frames).
# T's finished renders/ folder is 4.6 GB, but chunks and mattes in flight need several times that.
DISK_GB = {"ingest": 3, "transcribe": 1, "cut": 10, "build": 1, "render": 30}
EPILOG = "example: vedit doctor --json"


def add_args(sp) -> None:
    sp.epilog = EPILOG


def _first_line(text: str) -> str:
    return (text or "").strip().splitlines()[0] if (text or "").strip() else ""


def check_ffmpeg() -> tuple[str, str]:
    if not shutil.which("ffmpeg"):
        return "fail", "ffmpeg not found (brew install ffmpeg)"
    out = sh(["ffmpeg", "-hide_banner", "-encoders"], 30, check=False).stdout or ""
    missing = [e for e in ("h264_videotoolbox", "hevc_videotoolbox") if e not in out]
    if missing:
        return "fail", f"ffmpeg lacks {', '.join(missing)} (reinstall a VideoToolbox build)"
    return "ok", "ffmpeg with h264_videotoolbox + hevc_videotoolbox"


def check_ffprobe() -> tuple[str, str]:
    return ("ok", "ffprobe") if shutil.which("ffprobe") else ("fail", "ffprobe not found (comes with ffmpeg)")


def check_node() -> tuple[str, str]:
    if not (shutil.which("node") and shutil.which("npx")):
        return "fail", "node/npx not found (brew install node)"
    v = _first_line(sh(["node", "--version"], 15, check=False).stdout)
    return "ok", f"node {v}, npx"


def check_hyperframes() -> tuple[str, str]:
    if not shutil.which("npx"):
        return "fail", "hyperframes: npx missing"
    pin = versions.HYPERFRAMES
    p = sh(["npx", "--yes", f"hyperframes@{pin}", "--version"], 120, check=False)
    got = _first_line(p.stdout)
    if p.returncode != 0 or not got:
        return "fail", f"hyperframes@{pin} did not run (exit {p.returncode}); check network or npm"
    return "ok", f"hyperframes {got} (pinned {pin}); opencv pinned {versions.OPENCV}"


def check_studio() -> list[tuple[str, str]]:
    from vedit import studio  # imported here so tests can monkeypatch it

    try:
        st = studio.status()
    except VeditError as e:
        return [("fail", f"Studio unreachable: {e.message}"), ("warn", "qwen3-asr: unknown (Studio down)")]
    if not st.get("reachable", True):
        return [("fail", "Studio not reachable (open the Studio app)"), ("warn", "qwen3-asr: unknown")]
    q = st.get("queue") or {}
    out = [("ok", f"Studio up, queue {q.get('running', 0)} running / {q.get('queued', 0)} queued")]
    try:
        speech = {m.get("id"): m for m in studio.speech_models()}
    except VeditError as e:
        speech, why = None, e.message
    asr = (speech or {}).get("qwen3-asr-1.7b")
    if speech is None:
        out.append(("warn", f"qwen3-asr: unknown (`studio models --speech` failed: {why})"))
    elif asr is None:
        out.append(("fail", "qwen3-asr-1.7b not in Studio's speech models: update Studio"))
    elif asr.get("downloaded") and asr.get("loadable", True):
        out.append(("ok", "qwen3-asr-1.7b ready"))
    else:
        out.append(("fail", "qwen3-asr-1.7b not downloaded: download it in Studio (Settings -> Models)"))
    if studio.video_cutout_supported():
        out.append(("ok", "studio cutout takes video (big-word cut-outs)"))
    else:
        why = "cut-outs fall back to hyperframes remove-background (slower, keeps the shelf; masked)"
        fix = "update Studio (`make cli` in ~/Projects/New/studio)"
        out.append(("warn", f"studio cutout has no video mode: {why}; {fix}"))
    return out


def check_ollama() -> tuple[str, str]:
    if not shutil.which("ollama"):
        return "warn", "ollama not found (optional: local summaries)"
    return "ok", "ollama (optional)"


def check_disk(root: Path, stage: str) -> tuple[str, str]:
    need = DISK_GB[stage]
    free = shutil.disk_usage(root).free / 1e9
    if free < need:
        return "fail", f"disk: {free:.0f} GB free, {stage} needs ~{need} GB"
    lvl = "warn" if free < need * 1.5 else "ok"
    return lvl, f"disk: {free:.0f} GB free, {stage} needs ~{need} GB"


def run_checks(root: Path | None, stage: str) -> list[tuple[str, str]]:
    res = [check_ffmpeg(), check_ffprobe(), check_node(), check_hyperframes(), *check_studio()]
    res += [check_ollama(), check_disk(root or Path.cwd(), stage)]
    return res


def _next_stage(root: Path | None) -> str:
    if root is not None:
        try:
            project = Project.load(root)
            status = state.stage_status(project, project.paths)
            return next((s for s in state.STAGES if status[s] != "done"), "render")
        except ProjectError:
            pass
    return "render"  # no project: the worst case


def run_doctor(ns) -> Report:
    try:
        root = find_project(override=ns.project)
    except ProjectError:
        if ns.project:
            raise
        root = None
    stage = _next_stage(root)
    r = Report("doctor")
    for level, text in run_checks(root, stage):
        getattr(r, {"ok": "ok_"}.get(level, level))(text)
    r.data = {"project": str(root) if root else None, "next_stage": stage, "checks": r.items}
    if not r.ok:
        r.next = "fix the lines marked failed, then vedit doctor"
    elif root is None:
        r.next = "vedit new <video>  (or cd into a project and run vedit status)"
    else:
        r.next = "vedit status"
    return r


run = run_doctor  # command table contract: run(ns) -> Report
