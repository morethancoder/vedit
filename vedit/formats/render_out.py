"""Draft and final renders of a non-16:9 output (`.vedit/out/<id>/hf/`), and story segments.

- draft: draft quality, 30 fps, `.vedit/renders/draft-<id>.mp4` (the HUD mock in `vedit review` reads it)
- final: standard quality, 60 fps, at the output canvas (1080x1920 for 9:16), `.vedit/renders/<slug>-<id>.mp4`
- story: the final file is also split at pauses into segments no longer than the platform's limit,
  `.vedit/renders/<slug>-<id>-NN.mp4`

Each render is keyed by the output project's content hash and skipped when unchanged.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

from vedit import formats as fm
from vedit.commands.draft import DURATION_TOLERANCE, RENDER_TIMEOUT, hf_hash
from vedit.formats.compose_out import out_dir
from vedit.render.hf import render_cmd, render_env
from vedit.report import VeditError
from vedit.run import FF, enc_h264, ffprobe_duration, hash_of
from vedit.run import run as sh

SEG_MIN_GAP = 0.25  # s of silence a story cut must land in
SEG_TIMEOUT = 600


def target(paths, slug: str, oid: str, final: bool) -> Path:
    return Path(paths.renders) / (f"{slug}-{oid}.mp4" if final else f"draft-{oid}.mp4")


def render(paths, project, out, final: bool, log: Path, force: bool = False) -> dict:
    hf = out_dir(paths, out.id)
    if not (hf / "index.html").is_file():
        raise VeditError(f"output {out.id} is not built yet", next="vedit build", code="not_built")
    dst = target(paths, project.slug, out.id, final)
    key = hash_of(hf_hash(hf), "final" if final else "draft", "v1")
    kf = dst.with_suffix(".key")
    if not force and dst.is_file() and kf.is_file() and kf.read_text() == key:
        return {"id": out.id, "file": str(dst), "reused": True, "segments": _segments_on_disk(dst)}
    span = json.loads((hf / "manifest.json").read_text())["span"]
    want = span[1] - span[0]
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(".tmp.mp4")
    tmp.unlink(missing_ok=True)
    kw = {"quality": "standard", "fps": 60, "video_bitrate": "16M"} if final else {}
    sh(
        render_cmd(hf, tmp, **kw),
        timeout=RENDER_TIMEOUT,
        cwd=hf,
        log=log,
        env=render_env(parallel_stream=True),
    )
    got = ffprobe_duration(tmp)
    if got is None or abs(got - want) > DURATION_TOLERANCE:
        tmp.unlink(missing_ok=True)
        raise VeditError(f"output {out.id} rendered {got}s, expected {want:.1f}s", next="vedit build")
    tmp.replace(dst)
    kf.write_text(key)
    segs = []
    if final and out.kind == "story":
        segs = split_story(paths, project, out, dst, span, log)
    return {"id": out.id, "file": str(dst), "reused": False, "seconds": round(got, 2), "segments": segs}


def _segments_on_disk(dst: Path) -> list[str]:
    return sorted(str(p) for p in dst.parent.glob(dst.stem + "-[0-9][0-9].mp4"))


def cut_points(words: list[dict], t0: float, t1: float, max_s: float) -> list[float]:
    """Story cuts (output time) at pauses between words, each segment <= max_s, as long as it can be."""
    gaps = [(a["t1"] + b["t0"]) / 2 - t0 for a, b in itertools.pairwise(words)
            if b["t0"] - a["t1"] >= SEG_MIN_GAP and t0 < a["t1"] and b["t0"] < t1]  # fmt: skip
    total, cuts, at = t1 - t0, [], 0.0
    while total - at > max_s:
        fit = [g for g in gaps if at + 3.0 < g <= at + max_s]
        nxt = fit[-1] if fit else at + max_s
        cuts.append(round(nxt, 3))
        at = nxt
    return cuts


def split_story(paths, project, out, src: Path, span, log: Path) -> list[str]:
    limit = min(fm.platform(p)["max_s"] or 60 for p in out.platforms)
    pw = Path(paths.program) / "P.words.json"
    words = json.loads(pw.read_text(encoding="utf-8")) if pw.is_file() else []
    bounds = [0.0, *cut_points(words, span[0], span[1], limit), span[1] - span[0]]
    for old in _segments_on_disk(src):
        Path(old).unlink()
    files = []
    for n, (a, b) in enumerate(itertools.pairwise(bounds), 1):
        seg = src.parent / f"{src.stem}-{n:02d}.mp4"
        cmd = [*FF, "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", str(src),
               *enc_h264("16M", gop=60), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(seg)]  # fmt: skip
        sh(cmd, timeout=SEG_TIMEOUT, log=log)
        files.append(str(seg))
    return files
