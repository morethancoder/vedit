"""Program render: the edl as one video (the cut film the graphics sit on). Port of T tools/program.py.

Picture: every edl piece is one small mp4 in `.vedit/program/pieces/<hash>.mp4` (VideoToolbox decode + encode, the
same codec parameters for all, exactly round(len * fps) frames; a piece that runs past its camera's video end,
whose audio is longer, holds its last frame); a chapter hold is the frame at max(0, in - 0.04),
held. Changing one cut changes the hash of only the pieces it touches, so only those re-encode; the rest join in a
lossless concat. Sound: 48 kHz source audio, every cut a 60 ms equal-power crossfade, silent holds, a quadratic
fade from `fade_start`. The profile's mp4 muxes the concat video (copy) with AAC 256k.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import soundfile as sf

from vedit.report import VeditError
from vedit.run import DECODE, FF, RunError, hash_of, run, sample_hash

SR = 48000
HANDLE = 0.03  # each cut is a 60 ms equal-power crossfade centred on it
END_FADE = 1.6  # quadratic fade to silence from edl["fade_start"]
HOLD_BACK = 0.04  # a hold shows the frame just before its cut
SEEK_BIAS = 0.002  # seek a hair early so the frame exactly at `in` is kept
POOL = 4
VERSION = 1  # bump when the piece encoding changes: all pieces re-render

PROFILES = {
    "proxy": {
        "fps": 30,
        "size": "1920x1080",
        "pre": "",
        "post": "",
        "venc": ["-c:v", "h264_videotoolbox", "-b:v", "8M", "-g", "30", "-pix_fmt", "yuv420p"],
        "out": "proxy.mp4",
    },
    "master": {  # 720p camera, upscaled once
        "fps": 60,
        "size": "3840x2160",
        "pre": "fps=60,",
        "post": "scale=3840:2160:flags=lanczos",
        "venc": [
            "-c:v",
            "hevc_videotoolbox",
            "-q:v",
            "72",
            "-tag:v",
            "hvc1",
            "-g",
            "60",
            "-pix_fmt",
            "yuv420p",
        ],
        "out": "master.mp4",
    },
}


def frames_of(piece: dict, fps: int) -> int:
    """Frames a piece occupies: its hold, or its source length."""
    return round((piece["hold"] if "hold" in piece else piece["out"] - piece["in"]) * fps)


def source_video(paths, clip: str, profile: str) -> Path:
    src = paths.media / "proxy" / f"{clip}.mp4" if profile == "proxy" else paths.media / f"{clip}-cam.mp4"
    if not src.is_file():
        raise VeditError(f"missing {src}", next="vedit new <input>  (rebuilds media)")
    return src


def piece_hash(piece: dict, prof: dict, ident: str) -> str:
    """Hash of everything that decides a piece's pixels: encoding params, source identity, range, hold, fps,
    and the end pad (only a piece that runs past its video's end has one, so other hashes never change)."""
    params = {k: prof[k] for k in ("fps", "size", "pre", "post", "venc")}
    pad = ["pad"] if piece.get("pad") else []
    return hash_of(VERSION, params, ident, piece["clip"], round(piece["in"], 4), round(piece["out"], 4),
                   piece.get("hold", 0), prof["fps"], *pad)  # fmt: skip


def video_end(src: Path) -> float:
    """Seconds of the video stream (a camera's audio can run past it)."""
    try:
        out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=duration",
                   "-of", "csv=p=0", src], 60).stdout.strip()  # fmt: skip
        return float(out.split()[0])
    except (RunError, IndexError, ValueError):
        return float("inf")


def plan(edl: dict, paths, profile: str) -> list[tuple[dict, Path, Path]]:
    """[(piece, source video, piece file)] in program order."""
    prof, idents, out = PROFILES[profile], {}, []
    for p in edl["pieces"]:
        c = p["clip"]
        if c not in idents:
            src = source_video(paths, c, profile)
            idents[c] = (src, f"{src}:{sample_hash(src)}", video_end(src))
        src, ident, end = idents[c]
        if "hold" not in p and p["out"] - end > 0.5 / prof["fps"]:
            p = {**p, "pad": True}  # runs past the video: its last frame is held to the full length
        out.append((p, src, paths.program / "pieces" / f"{piece_hash(p, prof, ident)}.mp4"))
    return out


def render_piece(p: dict, src: Path, dst: Path, prof: dict, log: Path | None = None) -> None:
    fps, n = prof["fps"], frames_of(p, prof["fps"])
    tmp = dst.with_name(dst.stem + ".part.mp4")
    if "hold" in p:
        still = dst.with_name(dst.stem + ".png")
        t = max(0.0, p["in"] - HOLD_BACK)
        run([*FF, "-ss", f"{t:.3f}", "-i", src, "-frames:v", "1", "-s", prof["size"], still], 300, log=log)
        cmd = [
            *FF,
            "-loop",
            "1",
            "-framerate",
            str(fps),
            "-i",
            still,
            "-frames:v",
            str(n),
            *prof["venc"],
            tmp,
        ]
    else:
        vf = (prof["pre"] + prof["post"]).rstrip(",")
        if p.get("pad"):
            vf = ",".join(x for x in (vf, "tpad=stop_mode=clone:stop=-1") if x)
        cmd = [*FF, *DECODE, "-ss", f"{max(0.0, p['in'] - SEEK_BIAS):.4f}", "-i", src, "-an"]
        cmd += ["-vf", vf] if vf else []
        cmd += ["-frames:v", str(n), "-r", str(fps), *prof["venc"], tmp]
    run(cmd, 1800, log=log)
    tmp.rename(dst)
    if "hold" in p:
        still.unlink(missing_ok=True)


def render_pieces(items, prof, progress=None, log=None, workers: int = POOL) -> tuple[int, int]:
    """Render the missing piece files (a small pool). Returns (rendered, reused)."""
    (items[0][2].parent).mkdir(parents=True, exist_ok=True) if items else None
    todo, seen = [], set()
    for p, src, dst in items:
        if not dst.is_file() and dst not in seen:
            seen.add(dst)
            todo.append((p, src, dst))
    reused = len({d for _, _, d in items}) - len(todo)
    done = 0
    if progress:
        progress(0, len(todo))
    with ThreadPoolExecutor(workers) as ex:
        for fut in [ex.submit(render_piece, p, s, d, prof, log) for p, s, d in todo]:
            fut.result()
            done += 1
            if progress:
                progress(done, len(todo))
    return len(todo), reused


def mix(edl: dict, read) -> np.ndarray:
    """Stereo float32 program audio. `read(clip, i0, i1)` returns source samples [i0, i1) (clipped to the file).
    Each piece carries HANDLE of extra source each side and an equal-power ramp over 2 x HANDLE centred on its
    cut, so neighbours crossfade (never a dip to zero). Holds are silent; the end fades from fade_start."""
    total = round(edl["total"] * SR)
    out = np.zeros((total, 2), np.float32)
    h = int(HANDLE * SR)
    ramp = np.sin(np.linspace(0, np.pi / 2, 2 * h))[:, None].astype(np.float32)
    for p in edl["pieces"]:
        if "hold" in p:
            continue
        i0, i1 = round(p["in"] * SR) - h, round(p["out"] * SR) + h
        seg = np.zeros((i1 - i0, 2), np.float32)
        s0 = max(0, i0)
        a = read(p["clip"], s0, i1)
        seg[s0 - i0 : s0 - i0 + len(a)] = a
        seg[: 2 * h] *= ramp
        seg[-2 * h :] *= ramp[::-1]
        o0 = round(p["start"] * SR) - h
        c0, c1 = max(0, o0), min(total, o0 + len(seg))
        out[c0:c1] += seg[c0 - o0 : c1 - o0]
    f0 = int(edl["fade_start"] * SR)
    f1 = min(total, f0 + int(END_FADE * SR))
    if f1 > f0:
        out[f0:f1] *= np.linspace(1, 0, f1 - f0, dtype=np.float32)[:, None] ** 2
    out[f1:] = 0
    return out


def write_audio(edl: dict, paths, dst: Path | None = None) -> float:
    """Mix the project's 48 kHz WAVs into program/program.wav (PCM 24 stereo). Returns seconds."""
    files: dict[str, sf.SoundFile] = {}

    def read(clip, i0, i1):
        if clip not in files:
            files[clip] = sf.SoundFile(str(paths.media / f"{clip}-48k.wav"))
        f = files[clip]
        f.seek(min(i0, f.frames))
        a = f.read(max(0, i1 - i0), dtype="float32", always_2d=True)
        return a if a.shape[1] >= 2 else np.repeat(a, 2, axis=1)

    try:
        out = mix(edl, read)
    finally:
        for f in files.values():
            f.close()
    dst = dst or paths.program / "program.wav"
    dst.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(dst), out, SR, subtype="PCM_24")
    return len(out) / SR


def _count(path: Path, stream: str, entry: str) -> float:
    cmd = ["ffprobe", "-v", "error", "-select_streams", stream, "-count_packets", "-show_entries",
           f"stream={entry}", "-of", "csv=p=0", path]  # fmt: skip
    return float(run(cmd, 600).stdout.strip().split()[0])


def verify(path: Path, total: float, fps: int) -> dict:
    """Video frames vs round(total * fps) and audio length vs total."""
    frames = int(_count(path, "v:0", "nb_read_packets"))
    adur = float(run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=duration",
                      "-of", "csv=p=0", path], 60).stdout.strip())  # fmt: skip
    want = round(total * fps)
    return {"frames": frames, "want_frames": want, "audio_s": round(adur, 3),
            "ok": abs(frames - want) <= 1 and abs(adur - total) < 0.1}  # fmt: skip


def render(edl: dict, paths, profile: str = "proxy", progress=None, log: Path | None = None) -> dict:
    """Render `profile` ("proxy" | "master") from the edl. Returns what happened (for the report)."""
    prof, t0 = PROFILES[profile], time.time()
    paths.program.mkdir(parents=True, exist_ok=True)
    items = plan(edl, paths, profile)
    out = paths.program / prof["out"]
    stamp = out.with_name(out.name + ".stamp.json")
    wavs = {c: str(paths.media / f"{c}-48k.wav") for c in {p["clip"] for p in edl["pieces"]}}
    key = hash_of(
        VERSION, edl, [str(d) for _, _, d in items], {c: sample_hash(Path(w)) for c, w in wavs.items()}
    )
    try:
        old = json.loads(stamp.read_text())
    except (OSError, ValueError):
        old = {}
    if old.get("key") == key and out.is_file() and all(d.is_file() for _, _, d in items):
        # nothing changed since the last mux: no audio mix, encode or mux
        return {"profile": profile, "path": str(out), "pieces": len(items), "rendered": 0,
                "reused": len(items), "seconds": round(time.time() - t0, 1), "total": edl["total"],
                **old["verify"], "unchanged": True}  # fmt: skip
    stamp.unlink(missing_ok=True)
    write_audio(edl, paths)
    rendered, reused = render_pieces(items, prof, progress, log)
    lst = paths.program / f"{profile}-pieces.txt"
    lst.write_text("".join(f"file '{d}'\n" for _, _, d in items))
    run([*FF, "-f", "concat", "-safe", "0", "-i", lst, "-i", paths.program / "program.wav", "-map", "0:v",
         "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", out],
        1800, log=log)  # fmt: skip
    v = verify(out, edl["total"], prof["fps"])
    if v["ok"]:
        stamp.write_text(json.dumps({"key": key, "verify": v}))
    return {"profile": profile, "path": str(out), "pieces": len(items), "rendered": rendered, "reused": reused,
            "seconds": round(time.time() - t0, 1), "total": edl["total"], **v}  # fmt: skip


def load_edl(paths) -> dict:
    return json.loads((paths.edl / "edl.json").read_text())
