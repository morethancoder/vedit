"""The only door to local AI: thin wrappers over `studio --json …` with caching and clear errors."""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from vedit.report import VeditError
from vedit.run import RunError, hash_of, run

INSTALL = "install Studio (see ~/Projects/New/studio: `make cli`, then put bin/ on PATH)"
START_NOTE = "studio: started Studio"
# progress lines Studio prints on stderr with --wait: queue position, stages, percent, step 3/9
PROGRESS = re.compile(
    r"(^\[[0-9a-f]+\]|\d+\s*%|step\s+\d+/\d+|queue|queued|position|stage|running|waiting|uploading)",
    re.IGNORECASE,
)
DEFAULT_MODELS = {"ar": "qwen3-asr-1.7b"}  # en/other: Studio's `auto` picks


class StudioError(VeditError):
    """Studio is missing, unreachable, lacks a model, or the call failed."""


@dataclass
class Word:
    start: float
    end: float
    text: str


@dataclass
class Transcript:
    words: list[Word]
    segments: list[dict]
    warnings: list[str] = field(default_factory=list)
    model: str | None = None
    cache_path: Path | None = None
    cached: bool = False


def _need_studio() -> str:
    found = shutil.which("studio")
    if not found:
        raise StudioError("`studio` is not on PATH", next=INSTALL)
    return found


def _parse_error(stdout: str, stderr: str) -> tuple[str, int | None]:
    """Studio's `{"error":…,"exit":N}` (stdout or stderr) or a plain `studio: message` line."""
    for blob in (stderr, stdout):
        for line in reversed((blob or "").strip().splitlines()):
            line = line.strip()
            if line.startswith("{") and '"error"' in line:
                try:
                    d = json.loads(line)
                    return str(d["error"]), d.get("exit")
                except (ValueError, KeyError):
                    pass
    lines = [ln for ln in (stderr or "").strip().splitlines() if ln.strip()]
    return (lines[-1] if lines else "unknown error"), None


def _warnings(stderr: str) -> list[str]:
    out = []
    for ln in (stderr or "").splitlines():
        s = ln.strip()
        if not s or s.startswith((START_NOTE, "{")) or PROGRESS.search(s):
            continue
        out.append(s.removeprefix("studio: ").removeprefix("note: "))
    return out


def _classify(msg: str) -> StudioError:
    low = msg.lower()
    if any(
        k in low for k in ("not downloaded", "not installed", "isn't downloaded", "missing model", "download")
    ):
        return StudioError(
            f"Studio is missing a model: {msg}",
            next="download it in the Studio app (Settings -> Models), then run again",
        )
    if any(
        k in low
        for k in ("unreachable", "connection refused", "no server", "could not connect", "can't reach")
    ):
        return StudioError(
            f"Studio server unreachable: {msg}",
            next="start the Studio app (`make dev` in ~/Projects/New/studio) or check `studio status`",
        )
    return StudioError(f"studio failed: {msg}")


def _call(args: list[str], timeout: float, log: Path | None) -> tuple[str, list[str]]:
    """Run `studio --json ARGS`; return (stdout, warnings). Retries once, only when unreachable."""
    exe = _need_studio()
    for attempt in (0, 1):
        try:
            proc = run([exe, "--json", *args], timeout, log=log, check=False)
        except OSError as e:
            raise StudioError(f"cannot run studio: {e}", next=INSTALL) from e
        if proc.returncode == 0:
            return proc.stdout, _warnings(proc.stderr)
        if proc.returncode == 124:
            raise RunError(f"studio timed out after {timeout:g}s")
        msg, _ = _parse_error(proc.stdout, proc.stderr)
        err = _classify(msg)
        if attempt == 0 and err.message.startswith("Studio server unreachable"):
            continue
        raise err
    raise AssertionError("unreachable")


def _json(text: str) -> dict:
    try:
        d = json.loads(text)
    except ValueError as e:
        raise StudioError(f"studio printed invalid JSON: {text[:200]!r}") from e
    if isinstance(d, dict) and "error" in d and "exit" in d:
        raise _classify(str(d["error"]))
    return d


def parse_transcript(data: dict) -> tuple[list[Word], list[dict], str | None, list[str]]:
    """Accept `{"transcript": {...}}` (studio --json) or a bare transcript; return words, segments, model, warnings."""
    t = data.get("transcript", data)
    segments = t.get("segments", [])
    words = [
        Word(float(w["start"]), float(w["end"]), str(w["text"]))
        for sg in segments
        for w in sg.get("words", [])
    ]
    model = data.get("model") or t.get("model")
    warns = [str(w) for w in data.get("warnings") or t.get("warnings") or []]
    return words, segments, model, warns


def transcribe(
    path: Path,
    lang: str,
    dialect: str | None = None,
    hint: str | None = None,
    fillers: str = "keep",
    vad: bool = False,
    *,
    cache_dir: Path,
    model: str | None = None,
    timeout: float = 2400,
    log: Path | None = None,
) -> Transcript:
    """Word-timed transcript via Studio, cached by input content + options under cache_dir."""
    path = Path(path)
    model = model or DEFAULT_MODELS.get(lang)
    opts = {"lang": lang, "dialect": dialect, "hint": hint, "fillers": fillers, "vad": vad, "model": model}
    out = Path(cache_dir) / f"{hash_of(path, opts)}.json"
    if out.exists():
        words, segs, m, warns = parse_transcript(json.loads(out.read_text(encoding="utf-8")))
        return Transcript(words, segs, warns, m, out, cached=True)
    args = ["transcribe", str(path), "--lang", lang]
    if dialect:
        args += ["--dialect", dialect]
    if hint:
        args += ["--hint", hint]
    args += ["--fillers", fillers]
    if not vad:
        args.append("--no-vad")
    if model:
        args += ["--model", model]
    out.parent.mkdir(parents=True, exist_ok=True)
    # --timeout lets Studio stop waiting a little before our own time box
    args += ["-o", str(out), "--timeout", f"{max(1, int(timeout) - 30)}s"]
    stdout, stderr_warns = _call(args, timeout, log)
    if stdout.strip():
        _json(stdout)  # surfaces a JSON error form even on exit 0
    if not out.exists():
        raise StudioError(f"studio did not write {out}", next="run `studio status` and try again")
    data = json.loads(out.read_text(encoding="utf-8"))
    words, segs, m, warns = parse_transcript(data)
    if stdout.strip():
        stdout_data = json.loads(stdout)
        m = m or stdout_data.get("model")
        warns = warns or [str(w) for w in stdout_data.get("warnings") or []]
    warns = list(dict.fromkeys([*warns, *stderr_warns]))
    # keep warnings with the cache so a cache hit still reports them
    data.setdefault("warnings", warns)
    out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return Transcript(words, segs, warns, m, out, cached=False)


def cutout_image(
    path: Path, out: Path, model: str = "birefnet", *, timeout: float = 600, log: Path | None = None
) -> dict:
    """Transparent PNG cut-out of a still. Returns Studio's JSON plus `warnings`."""
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    stdout, warns = _call(["cutout", str(path), "--model", model, "--wait", "--out", str(out)], timeout, log)
    d = _json(stdout) if stdout.strip() else {}
    d["warnings"] = warns
    return d


def judge(
    text: str,
    *,
    yesno: str | list[str] | None = None,
    choices: dict[str, list[str]] | None = None,
    engine: str = "kev",
    timeout: float = 300,
    log: Path | None = None,
) -> dict:
    """Typed judgment. `choices` maps a question to its options. Returns Studio's JSON plus `warnings`."""
    args = ["judge", "--text", text, "--engine", engine]
    for q in [yesno] if isinstance(yesno, str) else (yesno or []):
        args += ["--yesno", q]
    for q, opts in (choices or {}).items():
        args += ["--choice", q, "--options", ",".join(opts)]
    stdout, warns = _call(args, timeout, log)
    d = _json(stdout)
    d["warnings"] = warns
    return d


def status(*, timeout: float = 120, log: Path | None = None) -> dict:
    """`studio --json status` (server reachable, installed/missing models) plus `warnings`."""
    stdout, warns = _call(["status"], timeout, log)
    d = _json(stdout)
    d["warnings"] = warns
    return d


def speech_models(*, timeout: float = 120, log: Path | None = None) -> list[dict]:
    """Speech models from `studio --json models --speech`: [{id, downloaded, loadable, ...}]."""
    stdout, _ = _call(["models", "--speech"], timeout, log)
    d = _json(stdout)
    return [m for m in d.get("models", []) if isinstance(m, dict)]


_VIDEO_CUTOUT: dict[str, bool] = {}


def video_cutout_supported(*, timeout: float = 30) -> bool:
    """True when the installed `studio cutout` takes a VIDEO (`--start/--duration`). Read from its --help, once."""
    exe = shutil.which("studio")
    if not exe:
        return False
    if exe not in _VIDEO_CUTOUT:
        try:
            p = run([exe, "cutout", "--help"], timeout, check=False)
            text = (p.stdout or "") + (p.stderr or "")
        except (OSError, RunError):
            text = ""
        _VIDEO_CUTOUT[exe] = "VIDEO" in text and "--duration" in text
    return _VIDEO_CUTOUT[exe]


def cutout_video(
    src: Path,
    start: float,
    dur: float,
    out: Path,
    model: str = "birefnet-lite",
    *,
    timeout: float = 3600,
    log: Path | None = None,
) -> dict:
    """Alpha video of the main person in `src[start, start+dur]`; `.webm` = VP9 alpha, `.mov` = ProRes 4444.

    Returns Studio's `video` block ({frames, fps, width, height, subject, model, ms_per_frame, ...}).
    """
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    args = ["cutout", str(src), "--start", f"{start:.3f}", "--duration", f"{dur:.3f}", "--model", model,
            "--out", str(out), "--timeout", f"{max(1, int(timeout) - 30)}s"]  # fmt: skip
    stdout, warns = _call(args, timeout, log)
    jobs = _json(stdout).get("jobs") or [{}]
    job = jobs[0]
    if job.get("status") not in (None, "done") or not Path(out).exists():
        raise StudioError(f"studio cutout did not write {out} (job {job.get('id')}: {job.get('status')})")
    return {**(job.get("video") or {}), "job": job.get("id"), "warnings": warns}
