"""One place that builds the HyperFrames `render` command line (draft, doodle preview, 4K master)."""

from __future__ import annotations

from pathlib import Path

from vedit.versions import HYPERFRAMES

QUALITIES = ("draft", "standard", "high")
RESOLUTIONS = ("1080p", "4k")


def render_cmd(
    project: Path | str,
    out: Path | str,
    *,
    quality: str = "draft",
    resolution: str = "1080p",
    fps: int | None = None,
    frames_cache_dir: Path | str | None = None,
    video_bitrate: str | None = None,
    quiet: bool = True,
    composition: str | None = None,
) -> list[str]:
    """`npx hyperframes@<pin> render <project> -o <out> ...` with `--gpu --browser-gpu` always.

    HyperFrames 0.8.170 has no start/end range flag: a partial render needs its own composition
    (`composition`, relative to `project`, e.g. `chunks/chunk-00.html`).
    Run it with cwd=project and a timeout (vedit.run.run); never start a Studio preview.

    Fast capture is always off. Our compositions use `filter: blur` (the A-roll under full-frame scenes), which
    drawElementImage cannot draw, so HyperFrames falls back to screenshots anyway; but for >= 900 frames it
    first picks single-worker fast capture and keeps that ONE worker after the fallback. Turning it off up front
    gives 3 screenshot workers: a 150 s draft chunk went from 322 s to 145 s (2026-11-06, docs/pipeline.md).
    """
    if quality not in QUALITIES:
        raise ValueError(f"quality {quality!r}: one of {', '.join(QUALITIES)}")
    if resolution not in RESOLUTIONS:
        raise ValueError(f"resolution {resolution!r}: one of {', '.join(RESOLUTIONS)}")
    cmd = ["npx", "--yes", f"hyperframes@{HYPERFRAMES}", "render", str(project), "-o", str(out)]
    if composition is not None:
        cmd += ["-c", composition]
    # a fixed bitrate (the 4K master, 60M as T) replaces the quality preset's CRF: the two are exclusive
    cmd += ["--video-bitrate", video_bitrate] if video_bitrate else ["-q", quality]
    cmd += ["--resolution", resolution]
    if fps is not None:
        cmd += ["-f", str(fps)]
    cmd += ["--gpu", "--browser-gpu", "--experimental-fast-capture=false"]
    if frames_cache_dir is not None:
        cmd += [f"--frames-cache-dir={frames_cache_dir}"]
    if quiet:
        cmd.append("--quiet")
    return cmd


def render_env(*, parallel_stream: bool = False) -> dict[str, str]:
    """Extra environment for a render (HF_CAPTURE_PARALLEL_STREAM: workers stream to the encoder, no disk path)."""
    return {"HF_CAPTURE_PARALLEL_STREAM": "true"} if parallel_stream else {}
