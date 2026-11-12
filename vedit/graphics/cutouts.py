"""Person cut-outs: The creator cut out of the program so a big word can sit behind his head.

`ensure(project, paths, ranges)` makes one alpha webm per range (`.vedit/mattes/<name>.webm`, 4K variant in
`.vedit/mattes/4k/`). A cut-out is stale only when its key changes: hash of (range to the ms, cut hash =
hash of the edl pieces, variant, method). The key sits beside the output (`<name>.key`); file dates and the
program's encoding never matter (a program re-encode with the same cut reuses the matte).

Method: `studio cutout VIDEO --start --duration --out x.webm` (birefnet-lite, largest person only, so the
bookshelf beside his head is not kept). When the installed Studio cannot cut out video (`vedit doctor` warns),
the old fallback runs (`# TEMP(studio-cutout)`): `hyperframes remove-background`, then a port of
T `tools/matte_mask.py` that limits the matte to a head ellipse around the tracked face plus the body below
the chin, minus shelf pixels. The method is part of the key, so switching methods rebuilds the cut-outs.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

from vedit import studio
from vedit.project import Paths
from vedit.report import VeditError
from vedit.run import DECODE, FF, RunError, _timeout_bin, enc_h264, ffprobe_json, hash_of, run
from vedit.versions import HYPERFRAMES

MODEL = "birefnet-lite"  # Studio's video default: ~6x faster than birefnet, clean at 1080p and 4K
METHOD = f"studio-cutout-{MODEL}"
FALLBACK = "hf-remove-background+head-mask-v1"  # TEMP(studio-cutout): only when Studio lacks video cut-out
DET_W, DET_H = 960, 540  # face detection size
LOW_W, LOW_H = 480, 270  # shelf-pass size
VARIANTS = {"proxy": ("proxy.mp4", ""), "4k": ("master.mp4", "4k")}
CUT_TIMEOUT = 300
REMOVE_TIMEOUT = 3600  # a person model on every frame (4K60: seconds per frame)
ENCODE_TIMEOUT = 1200


class Cutouts(dict):
    """name -> webm path, plus which were `reused` and which `rebuilt` (compose reports both)."""

    def __init__(self):
        super().__init__()
        self.reused: list[str] = []
        self.rebuilt: list[str] = []


def cut_hash(paths: Paths) -> str:
    """Hash of the edl pieces: the cut itself, not the program file."""
    f = paths.edl / "edl.json"
    try:
        pieces = json.loads(f.read_text())["pieces"]
    except (OSError, ValueError, KeyError) as e:
        raise VeditError(f"cannot read the cut from {f}: {e}", next="run `vedit cut` first") from e
    return hash_of(pieces)


def method() -> str:
    return METHOD if studio.video_cutout_supported() else FALLBACK


def key_of(start: float, dur: float, cut: str, variant: str, how: str = METHOD) -> str:
    return hash_of(f"{round(start, 3):.3f}", f"{round(dur, 3):.3f}", cut, variant, how)


def stale(paths: Paths, ranges: dict[str, tuple[float, float]], variant: str = "proxy") -> list[str]:
    """The cut-outs `ensure` would (re)build, without building or writing anything."""
    _src, sub = VARIANTS[variant]
    out_dir = paths.mattes / sub if sub else paths.mattes
    cut, how = cut_hash(paths), method()
    todo = []
    for name, (start, dur) in ranges.items():
        out, keyf = out_dir / f"{name}.webm", out_dir / f"{name}.key"
        ok = out.exists() and out.stat().st_size > 0 and keyf.exists()
        if not (ok and keyf.read_text().strip() == key_of(start, dur, cut, variant, how)):
            todo.append(name)
    return todo


def ensure(
    project,
    paths: Paths,
    ranges: dict[str, tuple[float, float]],
    variant: str = "proxy",
    log: Path | None = None,
) -> Cutouts:
    """Cut-out per `{name: (program_start, seconds)}`; rebuild only the ones whose key changed."""
    if variant not in VARIANTS:
        raise VeditError(f"unknown cut-out variant {variant!r}", next="use proxy or 4k")
    src_name, sub = VARIANTS[variant]
    src = paths.program / src_name
    out_dir = paths.mattes / sub if sub else paths.mattes
    cut, how = cut_hash(paths), method()
    result = Cutouts()
    for name, (start, dur) in ranges.items():
        out, keyf = out_dir / f"{name}.webm", out_dir / f"{name}.key"
        key = key_of(start, dur, cut, variant, how)
        result[name] = out
        if out.exists() and out.stat().st_size > 0 and keyf.exists() and keyf.read_text().strip() == key:
            result.reused.append(name)
            continue
        if not src.exists():
            raise VeditError(f"{src} is missing", next="run `vedit build` (program) first")
        out_dir.mkdir(parents=True, exist_ok=True)
        keyf.unlink(missing_ok=True)
        scratch = paths.vedit / "tmp" / f"cutout-{name}-{variant}"
        if how == METHOD:
            _studio_matte(src, start, dur, out, log)
        else:
            _make_matte(src, start, dur, out, scratch, log)
        keyf.write_text(key + "\n")
        result.rebuilt.append(name)
    return result


def _studio_matte(src: Path, start: float, dur: float, out: Path, log: Path | None) -> None:
    tmp = out.with_name(out.stem + ".tmp.webm")
    tmp.unlink(missing_ok=True)
    studio.cutout_video(src, start, dur, tmp, MODEL, timeout=REMOVE_TIMEOUT, log=log)
    tmp.replace(out)


# TEMP(studio-cutout): the fallback for a Studio without video cut-out (doctor warns); drop it with `mask_matte`
# once every machine runs a Studio that has it.
def _make_matte(src: Path, start: float, dur: float, out: Path, scratch: Path, log: Path | None) -> None:
    scratch.mkdir(parents=True, exist_ok=True)
    cut, raw, tmp = scratch / "src.mp4", scratch / "raw.webm", out.with_name(out.stem + ".tmp.webm")
    run(cut_cmd(src, start, dur, cut), CUT_TIMEOUT, log=log)
    # TEMP(studio-cutout): person model on the cut; also keeps the bookshelf, so the mask below follows
    run(remove_cmd(cut, raw), REMOVE_TIMEOUT, cwd=scratch, log=log)
    mask_matte(cut, raw, tmp, log)
    tmp.replace(out)
    for f in (cut, raw):
        f.unlink(missing_ok=True)


def cut_cmd(src: Path, start: float, dur: float, dst: Path) -> list[str]:
    """Cut the program range, VideoToolbox both ways (T used -ss after-input-free fast seek, 40M)."""
    return [
        *FF, *DECODE, "-ss", f"{start:.3f}", "-i", str(src), "-t", f"{dur:.3f}", "-an",
        *enc_h264("40M"), str(dst),
    ]  # fmt: skip


def remove_cmd(src: Path, dst: Path) -> list[str]:  # TEMP(studio-cutout)
    return ["npx", "--yes", f"hyperframes@{HYPERFRAMES}", "remove-background", str(src), "-o", str(dst),
            "--quality", "best"]  # fmt: skip


def encode_cmd(w: int, h: int, fps: str, dst: Path) -> list[str]:
    # The one CPU encode: VP9 with alpha has no VideoToolbox encoder (clips are a few seconds).
    return [
        *FF, "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{w}x{h}", "-r", fps, "-i", "-",
        "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "24",
        "-row-mt", "1", "-deadline", "good", "-cpu-used", "4", str(dst),
    ]  # fmt: skip


# ---- the head / body mask (port of T tools/matte_mask.py) ----


def smooth_track(boxes: list, k: int = 3) -> np.ndarray:
    """Fill frames without a face by interpolation, then a median of k. Rows are [x, y, w, h]."""
    known = [i for i, b in enumerate(boxes) if b is not None]
    if not known:
        raise VeditError("no face found in the cut-out range", next="check the range shows his face")
    arr = np.array([boxes[i] for i in known], dtype=float)
    track = np.stack([np.interp(range(len(boxes)), known, arr[:, c]) for c in range(4)], axis=1)
    pad = np.pad(track, ((k // 2, k // 2), (0, 0)), mode="edge")
    return np.array([np.median(pad[i : i + k], axis=0) for i in range(len(track))])


def shapes(box, xx, yy, s: float = 1.0):
    """(head ellipse, tighter head ellipse, body below the chin, chin y) for one face box."""
    x, y, w, h = np.asarray(box, dtype=float) * s
    cx, cy = x + w / 2, y + h / 2
    head = ((xx - cx) / (0.62 * w)) ** 2 + ((yy - (cy - 0.15 * h)) / (0.98 * h)) ** 2 <= 1
    tight = ((xx - cx) / (0.5 * w)) ** 2 + ((yy - (cy - 0.1 * h)) / (0.9 * h)) ** 2 <= 1
    below = yy - (y + 0.9 * h)
    body = (below > 0) & (np.abs(xx - cx) < np.minimum(0.5 * w + 2.4 * below, 2.9 * w))
    return head, tight, body, y + h


def shelf_of(counts: np.ndarray, n: int, size: tuple[int, int]) -> np.ndarray:
    """Pixels the model kept in more than 12% of frames outside head and body: the shelf (dilated, full size)."""
    lo = cv2.dilate((counts > 0.12 * n).astype(np.uint8), np.ones((9, 9), np.uint8))
    return cv2.resize(lo, size, interpolation=cv2.INTER_NEAREST).astype(bool)


def keep_mask(box, shelf: np.ndarray, xx, yy) -> np.ndarray:
    """Feathered 0..1 mask: head and body, minus shelf pixels that are not inside the tight head."""
    head, tight, body, _ = shapes(box, xx, yy)
    keep = (head | body) & ~(shelf & ~tight)
    feather = max(3, int(xx.shape[1] / 160)) | 1
    return cv2.GaussianBlur(keep.astype(np.float32), (feather * 4 + 1, feather * 4 + 1), feather)


def _frames(path: Path, w: int, h: int, fmt: str, decoder: str | None = None, timeout: float = 600):
    """Raw frames from ffmpeg (timeout + nice); `rgba` -> (h, w, 4), `gray` -> (h, w, 1)."""
    cmd = ["ffmpeg", "-v", "error", *(["-c:v", decoder] if decoder else []), "-i", str(path),
           "-f", "rawvideo", "-pix_fmt", fmt, "-s", f"{w}x{h}", "-"]  # fmt: skip
    tbin = _timeout_bin()
    full = ([tbin, str(timeout)] if tbin else []) + ["nice", "-n", "19", *cmd]
    p = subprocess.Popen(full, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE)
    size = w * h * (4 if fmt == "rgba" else 1)
    try:
        while len(buf := p.stdout.read(size)) == size:
            yield np.frombuffer(buf, np.uint8).reshape(h, w, 4 if fmt == "rgba" else 1)
    finally:
        p.stdout.close()
        p.wait()


def _fps(path: Path) -> str:
    vs = next(s for s in ffprobe_json(path)["streams"] if s["codec_type"] == "video")
    return vs["r_frame_rate"]


def mask_matte(src: Path, matte: Path, out: Path, log: Path | None = None) -> None:  # TEMP(studio-cutout)
    """Limit the model's matte to the creator (head ellipse + body, minus the shelf); VP9 alpha encode on the CPU."""
    vs = next(s for s in ffprobe_json(matte)["streams"] if s["codec_type"] == "video")
    w, h = int(vs["width"]), int(vs["height"])
    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    boxes = []
    for g in _frames(src, DET_W, DET_H, "gray"):
        f = cascade.detectMultiScale(g[:, :, 0], scaleFactor=1.1, minNeighbors=6, minSize=(60, 60))
        boxes.append(max(f, key=lambda b: b[2] * b[3]).astype(float) * (w / DET_W) if len(f) else None)
    track = smooth_track(boxes)

    # pass 1: "person" pixels that stay put outside head and body are the bookshelf
    ly, lx = np.mgrid[0:LOW_H, 0:LOW_W].astype(np.float32)
    count, n = np.zeros((LOW_H, LOW_W), np.float32), 0
    for i, fr in enumerate(_frames(matte, LOW_W, LOW_H, "rgba", decoder="libvpx-vp9")):
        _, tight, body, chin = shapes(track[min(i, len(track) - 1)], lx, ly, LOW_W / w)
        count += (fr[:, :, 3] > 100) & ~(tight | body) & (ly < chin + 0.3 * (chin - ly.min()))
        n += 1
    shelf = shelf_of(count, max(n, 1), (w, h))

    # pass 2: mask the alpha and encode (stdin pipe: run() cannot stream, so Popen under timeout + nice)
    tbin = _timeout_bin()
    cmd = encode_cmd(w, h, _fps(matte), out)
    full = ([tbin, str(ENCODE_TIMEOUT)] if tbin else []) + ["nice", "-n", "19", *cmd]
    enc = subprocess.Popen(full, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    try:
        for i, fr in enumerate(_frames(matte, w, h, "rgba", decoder="libvpx-vp9")):
            fr = fr.copy()
            m = keep_mask(track[min(i, len(track) - 1)], shelf, xx, yy)
            fr[:, :, 3] = (fr[:, :, 3].astype(np.float32) * m).astype(np.uint8)
            enc.stdin.write(fr.tobytes())
    finally:
        enc.stdin.close()
        err = enc.stderr.read().decode(errors="replace")
        enc.wait()
    if enc.returncode != 0:
        raise RunError("ffmpeg (vp9 alpha encode) failed:\n" + "\n".join(err.strip().splitlines()[-12:]))
