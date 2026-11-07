"""Reference images for a draft: copied from a folder (or one image), or sampled from a video at scene changes.

A video is scanned once with ffmpeg's scene score on a small decode (VideoToolbox); up to MAX_FRAMES of the
detected changes, spread evenly over the video, are grabbed at full size. Too few changes (a talking head, a
screen recording) -> frames evenly spaced instead.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from vedit.report import VeditError
from vedit.run import DECODE, ffprobe_duration, frame_grab, run

IMAGES = {".png", ".jpg", ".jpeg", ".webp"}
VIDEOS = {".mp4", ".mov", ".mkv", ".webm", ".m4v"}
MAX_FRAMES = 8
MAX_IMAGES = 16
SCENE = 0.3  # ffmpeg scene score that counts as a change
SCAN_TIMEOUT = 900


def images_in(d: Path) -> list[Path]:
    return sorted(f for f in Path(d).iterdir() if f.is_file() and f.suffix.lower() in IMAGES)


def scene_times(video: Path, log: Path | None = None) -> list[float]:
    """Seconds of every scene change (score > SCENE), from a 320 px wide decode."""
    vf = f"scale=320:-2,select='gt(scene,{SCENE})',showinfo"
    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-nostats",
        "-v",
        "info",
        *DECODE,
        "-i",
        str(video),
        "-an",
        "-vf",
        vf,
        "-f",
        "null",
        "-",
    ]
    proc = run(cmd, SCAN_TIMEOUT, log=log, check=False)
    return [float(t) for t in re.findall(r"pts_time:([\d.]+)", proc.stderr or "")]


def spread(times: list[float], n: int) -> list[float]:
    """n of `times`, evenly spread over the list (all when there are n or fewer)."""
    if len(times) <= n:
        return list(times)
    return [times[round(i * (len(times) - 1) / (n - 1))] for i in range(n)] if n > 1 else [times[0]]


def sample_video(video: Path, dst: Path, n: int = MAX_FRAMES, log: Path | None = None) -> list[Path]:
    dur = ffprobe_duration(video)
    times = [t for t in scene_times(video, log) if 0.5 < t < dur - 0.2]
    if len(times) < 3:  # too few cuts: evenly spaced instead
        times = [dur * (i + 0.5) / n for i in range(n)]
    out = []
    for i, t in enumerate(spread(times, n)):
        out.append(frame_grab(video, t + 0.1, dst / f"frame-{i + 1:02d}-{t:07.2f}s.png", log=log))
    return out


def gather(src: Path, dst: Path, log: Path | None = None) -> tuple[list[Path], str]:
    """Copy or sample refs from `src` (folder, image or video) into `dst`; (files, how)."""
    src = Path(src).expanduser()
    dst.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        files = images_in(src)[:MAX_IMAGES]
        if not files:
            raise VeditError(f"{src} has no images ({', '.join(sorted(IMAGES))})", exit=2)
        out = []
        for f in files:
            shutil.copyfile(f, dst / f.name)
            out.append(dst / f.name)
        return out, f"{len(out)} images copied from {src}"
    if src.is_file() and src.suffix.lower() in IMAGES:
        shutil.copyfile(src, dst / src.name)
        return [dst / src.name], f"1 image copied from {src}"
    if src.is_file() and src.suffix.lower() in VIDEOS:
        out = sample_video(src, dst, log=log)
        return out, f"{len(out)} frames sampled at scene changes of {src.name}"
    raise VeditError(
        f"--from {src}: not a folder of images, an image or a video",
        next="vedit style new <name> --from <folder of screenshots | video>",
        exit=2,
    )
