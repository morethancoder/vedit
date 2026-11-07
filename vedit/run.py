"""Time-boxed subprocess runner, content hashing and ffmpeg presets (VideoToolbox only)."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

from vedit.report import VeditError

TAIL_LINES = 12


class RunError(VeditError):
    """An external command failed or timed out."""


def _timeout_bin() -> str | None:
    found = shutil.which("timeout") or shutil.which("gtimeout")
    if found:
        return found
    local = Path.home() / ".local" / "bin" / "timeout"
    return str(local) if local.exists() else None


def log_path(root: Path, command: str) -> Path:
    """`<project>/.vedit/logs/<command>.log`."""
    return Path(root) / ".vedit" / "logs" / f"{command}.log"


def run(
    cmd: list[str],
    timeout: float,
    *,
    cwd=None,
    log: Path | None = None,
    check: bool = True,
    capture: bool = True,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run `cmd` under `timeout <s> nice -n 19` with stdin closed; raise RunError on failure."""
    cmd = [str(c) for c in cmd]
    tbin = _timeout_bin()
    full = [tbin, str(timeout), "nice", "-n", "19", *cmd] if tbin else ["nice", "-n", "19", *cmd]
    out = subprocess.PIPE if capture else None
    try:
        proc = subprocess.run(
            full,
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=out,
            text=True,
            errors="replace",
            cwd=cwd,
            env={**os.environ, **env} if env else None,
            timeout=None if tbin else timeout,
        )
    except subprocess.TimeoutExpired as e:
        proc = subprocess.CompletedProcess(full, 124, "", _text(e.stderr))
    stderr = proc.stderr or ""
    if log is not None:
        log = Path(log)
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as f:
            f.write(f"$ {' '.join(cmd)}\n{stderr}")
            if stderr and not stderr.endswith("\n"):
                f.write("\n")
    if check and proc.returncode != 0:
        why = (
            f"timed out after {timeout:g}s (exit 124)"
            if proc.returncode == 124
            else f"exit {proc.returncode}"
        )
        tail = "\n".join(stderr.strip().splitlines()[-TAIL_LINES:])
        code = {124: "timeout", 127: "missing_tool"}.get(proc.returncode, "failed")
        raise RunError(f"{Path(cmd[0]).name} failed: {why}" + (f"\n{tail}" if tail else ""), code=code)
    return proc


def _text(v) -> str:
    return v.decode(errors="replace") if isinstance(v, bytes) else (v or "")


def hash_of(*parts) -> str:
    """sha256 hex (first 16) over str/bytes/Path (file content)/dict/list (stable JSON)."""
    h = hashlib.sha256()
    for p in parts:
        if isinstance(p, Path):
            with p.open("rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
        elif isinstance(p, bytes):
            h.update(p)
        elif isinstance(p, str):
            h.update(p.encode())
        else:
            h.update(json.dumps(p, sort_keys=True, ensure_ascii=False, default=str).encode())
        h.update(b"\x00")
    return h.hexdigest()[:16]


SAMPLE = 1 << 20


def sample_hash(path: Path) -> str | None:
    """Cheap fingerprint of a big file: size + first 1 MiB + last 1 MiB. None when it is missing."""
    try:
        with Path(path).open("rb") as f:
            size = f.seek(0, 2)
            f.seek(0)
            head = f.read(SAMPLE)
            tail = b""
            if size > SAMPLE:
                f.seek(max(SAMPLE, size - SAMPLE))
                tail = f.read(SAMPLE)
    except OSError:
        return None
    return hash_of(str(size), head, tail)


# ---- ffmpeg presets (numbers lifted from T scripts/source.sh) ----

FF = ["ffmpeg", "-v", "error", "-y"]
DECODE = ["-hwaccel", "videotoolbox"]


def enc_h264(bitrate: str | None = "8M", quality: int | None = None, gop: int = 30) -> list[str]:
    """h264_videotoolbox: `-b:v 8M -g 30` (proxy) or `-q:v 75 -g 50` (cam, pass quality=75, gop=50)."""
    rate = ["-q:v", str(quality)] if quality is not None else ["-b:v", str(bitrate)]
    return ["-c:v", "h264_videotoolbox", *rate, "-g", str(gop)]


def enc_hevc(bitrate: str = "20M") -> list[str]:
    return ["-c:v", "hevc_videotoolbox", "-b:v", bitrate, "-tag:v", "hvc1"]


def enc_prores(profile: int = 3) -> list[str]:
    """prores_videotoolbox; profile 3 = 422 HQ."""
    return ["-c:v", "prores_videotoolbox", "-profile:v", str(profile)]


def proxy_1080p30(src: Path, dst: Path, timeout: float = 1800, log: Path | None = None) -> Path:
    """1080p 30 fps h264 8M, aac 192k, faststart (T source.sh proxy)."""
    cmd = [
        *FF, *DECODE, "-i", str(src),
        "-vf", "scale=1920:1080:flags=lanczos,fps=30",
        *enc_h264("8M", gop=30),
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(dst),
    ]  # fmt: skip
    run(cmd, timeout, log=log)
    return Path(dst)


def wav48k(
    src: Path, dst: Path, start: float | None = None, dur: float | None = None, mono: bool = True,
    timeout: float = 300, log: Path | None = None,
) -> Path:  # fmt: skip
    """48 kHz PCM WAV; mono by default (T source.sh used stereo: pass mono=False)."""
    cmd = [*FF]
    if start is not None:
        cmd += ["-ss", f"{start:.3f}"]
    cmd += ["-i", str(src)]
    if dur is not None:
        cmd += ["-t", f"{dur:.3f}"]
    cmd += ["-vn", "-ar", "48000", "-ac", "1" if mono else "2", "-c:a", "pcm_s16le", str(dst)]
    run(cmd, timeout, log=log)
    return Path(dst)


def frame_grab(src: Path, t: float, dst: Path, timeout: float = 60, log: Path | None = None) -> Path:
    """One still at time t (`-ss` before `-i`: fast seek)."""
    cmd = [*FF, "-ss", f"{t:.3f}", "-i", str(src), "-frames:v", "1", "-q:v", "2", str(dst)]
    run(cmd, timeout, log=log)
    return Path(dst)


def ffprobe_json(path: Path, timeout: float = 60) -> dict:
    cmd = ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    return json.loads(run(cmd, timeout).stdout)


def ffprobe_duration(path: Path, timeout: float = 60) -> float:
    cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)]
    return float(run(cmd, timeout).stdout.strip())
