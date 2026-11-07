"""The 4K60 master: 4K program + 4K cut-outs, then the film in ~150 s HyperFrames chunks, joined (port of T
`scripts/render.sh`; numbers and measurements in docs/pipeline.md).

Full-frame only: the overlay-only spike measured 1.16x and was not adopted (plans/phase-04-graphics).

Layout (what `vedit clean` knows):
- `.vedit/renders/hf/`        render project: links to `.vedit/hf/` compositions + assets, media -> 4K files,
                              `index.html` = the chunk being rendered (`.vedit/hf/chunks/chunk-NN.html`)
- `.vedit/renders/chunks/`    `chunk-NN.mp4` + `chunk-NN.key` (finished chunks; a rerun keeps them = resume)
- `.vedit/cache/frames/`      HyperFrames frame cache of the running chunk, deleted after each chunk
- `.vedit/renders/master.mp4` the joined, verified master

A chunk is reused only when its key (chunk HTML, every composition/asset it can read, the 4K program cut and
cut-out keys) is unchanged; file dates never count.
"""

from __future__ import annotations

import itertools
import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path

from vedit.graphics import compose, cutouts
from vedit.render.hf import render_cmd, render_env
from vedit.report import VeditError
from vedit.run import FF, RunError, _timeout_bin, hash_of, run, sample_hash
from vedit.versions import HYPERFRAMES

FPS = 60
BITRATE = "60M"
CHUNK_TIMEOUT = 6 * 3600  # one 150 s chunk took 9-12 min measured; generous for a loaded machine
JOIN_TIMEOUT = 1800
CACHE_PEAK = 3.5e9  # streamed 150 s chunk frame cache peaked at 3.2 GB (2026-11-05)
HF_WORK = 2.5e9  # HyperFrames' own work dir during a chunk
PROGRESS_RE = re.compile(r"@hf-progress (\{.*\})")


def layout(paths) -> dict[str, Path]:
    r = paths.vedit / "renders"
    return {
        "hf": r / "hf",
        "chunks": r / "chunks",
        "cache": paths.vedit / "cache" / "frames",
        "master": r / "master.mp4",
        "work": paths.vedit / "tmp" / "render",
    }


def load_chunks(paths) -> dict:
    f = paths.hf / "chunks.json"
    try:
        d = json.loads(f.read_text())
    except (OSError, ValueError) as e:
        raise VeditError(f"cannot read {f}: {e}", next="run `vedit build` first") from e
    if "mattes" not in d or "total" not in d:
        raise VeditError(f"{f} is from an older build (no cut-out ranges)", next="run `vedit build` again")
    return d


# ---- disk ----


def disk_need(total: float, done_chunks: int, n_chunks: int, have_program: bool) -> float:
    """Bytes the render still needs: 4K program (~45 Mb/s HEVC, pieces kept beside it: x2), chunks + master at
    60 Mb/s, one frame cache + HyperFrames work dir, the join's 24-bit PCM, 4K cut-outs."""
    left = (n_chunks - done_chunks) / max(n_chunks, 1)
    program = 0 if have_program else 2 * total * 45e6 / 8
    pcm = total * 48000 * 3 * 2
    return program + total * 60e6 / 8 * left + total * 60e6 / 8 + CACHE_PEAK + HF_WORK + pcm + 0.5e9


def check_disk(paths, need: float) -> float:
    free = shutil.disk_usage(paths.vedit).free
    if free < need * 1.1:
        raise VeditError(
            f"not enough disk: {free / 1e9:.0f} GB free, the render needs ~{need / 1e9:.0f} GB",
            next="free space (`vedit clean`, or delete other projects' renders), then run `vedit render` again",
            code="no_disk",
        )
    return free


# ---- render project ----


def link(src: Path, dst: Path) -> None:
    compose.link(src, dst)


def prepare(paths, mattes: dict[str, Path], lay: dict[str, Path]) -> Path:
    """`.vedit/renders/hf/`: same compositions/assets as the build, media pointing at the 4K files."""
    hf, out = paths.hf, lay["hf"]
    out.mkdir(parents=True, exist_ok=True)
    for d in ("compositions", "assets", "custom"):
        if (hf / d).exists():
            link(hf / d, out / d)
    for name in ("hyperframes.json", "package.json"):
        if (hf / name).is_file():
            shutil.copyfile(hf / name, out / name)
    media = out / "media"
    if media.is_symlink():
        media.unlink()
    media.mkdir(exist_ok=True)
    want = set()
    for f in (hf / "media").iterdir():
        if f.name == "program.mp4":
            src = paths.program / "master.mp4"
        elif f.stem in mattes:
            src = mattes[f.stem]
        else:
            src = f.resolve()
        link(src, media / f.name)
        want.add(f.name)
    for f in media.iterdir():
        if f.name not in want:
            f.unlink()
    return out


def tree_hash(root: Path) -> str:
    """Content hash of every file under root (compositions, assets, custom/); big files by sample hash."""
    if not root.exists():
        return ""
    files = sorted(p for p in root.rglob("*") if p.is_file())
    return hash_of(*[(str(p.relative_to(root)), sample_hash(p)) for p in files])


def static_key(paths, hf: Path) -> str:
    """Everything a chunk reads besides its own HTML: compositions, assets, custom/, every media file (the 4K
    program by its render stamp, cut-outs and plug media by content), the HyperFrames pin and the settings."""
    stamp = paths.program / "master.mp4.stamp.json"
    try:
        prog = json.loads(stamp.read_text())["key"]
    except (OSError, ValueError, KeyError):
        prog = sample_hash(paths.program / "master.mp4")
    media = {f.name: (prog if f.name == "program.mp4" else sample_hash(f.resolve()))
             for f in sorted((hf / "media").iterdir())}  # fmt: skip
    trees = [tree_hash(paths.hf / d) for d in ("compositions", "assets", "custom")]
    return hash_of(trees, media, HYPERFRAMES, FPS, BITRATE)


def chunk_key(html: str, static: str) -> str:
    return hash_of(html, static)


def kill_stale(job: dict | None) -> bool:
    """A render job that died (SIGKILL) can leave its HyperFrames process group running: stop it before resuming."""
    pg = ((job or {}).get("progress") or {}).get("child")
    if not pg:
        return False
    try:
        out = subprocess.run(["ps", "-A", "-o", "pgid=,command="], check=False, capture_output=True, text=True,
                             stdin=subprocess.DEVNULL, timeout=10).stdout  # fmt: skip
        ps = "\n".join(ln for ln in out.splitlines() if ln.split(None, 1)[:1] == [str(pg)])
    except (OSError, subprocess.SubprocessError):
        return False
    if "hyperframes" not in ps:
        return False  # pid reused by something else, or already gone
    try:
        os.killpg(pg, signal.SIGTERM)
        time.sleep(3)
        os.killpg(pg, signal.SIGKILL)
    except ProcessLookupError:
        pass
    return True


# ---- one chunk ----


def capture_progress(text: str) -> tuple[int, int] | None:
    """The last `@hf-progress {"code":"capture","done":i,"total":n}` line HyperFrames printed, as (i, n)."""
    last = None
    for m in PROGRESS_RE.finditer(text):
        try:
            d = json.loads(m.group(1))
        except ValueError:
            continue
        if d.get("code") == "capture" and d.get("total"):
            last = (int(d["done"]), int(d["total"]))
    return last


def _watch(log: Path, stop: threading.Event, report, start: int = 0, every: float = 5) -> None:
    """Follow the render log from `start` (this chunk's first byte: earlier lines are other tools' counters)
    and report HyperFrames' capture progress."""
    pos = start
    while not stop.wait(every):
        try:
            with open(log, "rb") as f:
                f.seek(pos)
                data = f.read()
        except OSError:
            continue
        cut = data.rfind(b"\n") + 1  # a half-written last line is read again next time
        pos += cut
        hit = capture_progress(data[:cut].decode(errors="replace"))
        if hit:
            report(*hit)


def probe(path: Path) -> dict:
    """frames (packets), size, fps and audio duration of an mp4."""
    vs = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets", "-show_entries",
              "stream=nb_read_packets,width,height,r_frame_rate", "-of", "json", path], 900).stdout  # fmt: skip
    v = json.loads(vs)["streams"][0]
    a = run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=duration",
             "-of", "csv=p=0", path], 60).stdout.strip()  # fmt: skip
    return {"frames": int(v["nb_read_packets"]), "size": f"{v['width']}x{v['height']}",
            "fps": v["r_frame_rate"], "audio_s": float(a or 0)}  # fmt: skip


def check_chunk(path: Path, seconds: float) -> dict:
    p = probe(path)
    want = round(seconds * FPS)
    p["want_frames"] = want
    p["ok"] = abs(p["frames"] - want) <= 1 and p["size"] == "3840x2160" and p["audio_s"] > 0
    return p


def render_chunk(hf: Path, out: Path, cache: Path, log: Path, report=None, on_start=None) -> None:
    """Render `hf/index.html` at 4K60 to `out` (via out.tmp.mp4), with its own frame cache, deleted after."""
    tmp = out.with_name(out.stem + ".tmp.mp4")
    tmp.unlink(missing_ok=True)
    shutil.rmtree(cache, ignore_errors=True)
    cmd = render_cmd(
        hf, tmp, resolution="4k", fps=FPS, frames_cache_dir=cache, video_bitrate=BITRATE, quiet=False
    )
    tbin = _timeout_bin()
    full = ([tbin, str(CHUNK_TIMEOUT)] if tbin else []) + ["nice", "-n", "19", *cmd]
    env = {**os.environ, **render_env(parallel_stream=True)}
    stop = threading.Event()
    with open(log, "ab") as lf:
        lf.write(f"$ {' '.join(cmd)}\n".encode())
        lf.flush()
        start = lf.tell()
        # own process group (= proc.pid): killed as a whole if this job stops, and found again by kill_stale
        proc = subprocess.Popen(full, cwd=hf, stdin=subprocess.DEVNULL, stdout=lf, stderr=lf, env=env,
                                start_new_session=True)  # fmt: skip
        if on_start:
            on_start(proc.pid)
        th = threading.Thread(target=_watch, args=(log, stop, report, start), daemon=True) if report else None
        if th:
            th.start()
        try:
            code = proc.wait()
        finally:
            stop.set()
            if th:
                th.join()
            if proc.poll() is None:
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
    shutil.rmtree(cache, ignore_errors=True)
    if code != 0 or not tmp.is_file() or tmp.stat().st_size == 0:
        tmp.unlink(missing_ok=True)
        raise RunError(f"hyperframes render of {out.name} failed (exit {code}); see {log}")
    tmp.replace(out)


# ---- join + verify ----


def join(parts: list[Path], secs: list[float], out: Path, work: Path, log: Path) -> Path:
    """Video joined losslessly; audio from each chunk's PCM in one AAC 320k pass; +faststart (T render.sh).
    Each chunk's PCM is padded/trimmed to its exact length, so AAC priming never drifts across joins.
    Writes and returns `out.tmp.mp4`; the caller renames it after the check."""
    work.mkdir(parents=True, exist_ok=True)
    vlist, alist = work / "video.txt", work / "audio.txt"
    wavs = []
    for p, sec in zip(parts, secs, strict=True):
        w = work / (p.stem + ".wav")
        run([*FF, "-i", p, "-vn", "-af", "apad", "-t", f"{sec:.4f}", "-c:a", "pcm_s24le", "-ar", "48000", w],
            600, log=log)  # fmt: skip
        wavs.append(w)
    vlist.write_text("".join(f"file '{p}'\n" for p in parts))
    alist.write_text("".join(f"file '{w}'\n" for w in wavs))
    tmp = out.with_name(out.stem + ".tmp.mp4")
    run([*FF, "-f", "concat", "-safe", "0", "-i", vlist, "-f", "concat", "-safe", "0", "-i", alist,
         "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "320k", "-movflags", "+faststart",
         tmp], JOIN_TIMEOUT, log=log)  # fmt: skip
    for w in wavs:
        w.unlink(missing_ok=True)
    return tmp


def verify(path: Path, total: float) -> dict:
    """frames = round(duration x 60) (±1), 3840x2160, audio as long as the film."""
    p = probe(path)
    want = round(total * FPS)
    ok = abs(p["frames"] - want) <= 1 and p["size"] == "3840x2160" and abs(p["audio_s"] - total) < 0.1
    return {**p, "audio_s": round(p["audio_s"], 3), "want_frames": want, "ok": ok}


# ---- the whole job ----


def render(project, paths, progress, log: Path) -> dict:
    """Run every stage; `progress(**fields)` publishes to state.json. Returns timings + verify."""
    from vedit.cut import program

    lay, t = layout(paths), {}
    ch = load_chunks(paths)
    bounds, total = ch["bounds"], ch["total"]
    n = len(bounds) - 1
    lay["chunks"].mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    progress(step="program", chunk=0, chunks=n)
    edl = program.load_edl(paths)
    prog = program.render(edl, paths, "master", log=log,
                          progress=lambda d, k: progress(step="program", piece=d, pieces=k))  # fmt: skip
    if not prog.get("ok", True):
        raise VeditError(f"4K program failed its check: {prog}", next=f"see {log}")
    t["program"] = round(time.time() - t0, 1)

    t0 = time.time()
    progress(step="cut-outs", piece=None, pieces=None)
    ranges = {k: tuple(v) for k, v in ch["mattes"].items()}
    mattes = cutouts.ensure(project, paths, ranges, variant="4k", log=log)
    t["cutouts"] = round(time.time() - t0, 1)

    hf = prepare(paths, dict(mattes), lay)
    static = static_key(paths, hf)
    parts, chunk_t, reused = [], [], 0
    for i in range(n):
        src = paths.hf / "chunks" / f"chunk-{i:02d}.html"
        html = src.read_text(encoding="utf-8")
        out, keyf = lay["chunks"] / f"chunk-{i:02d}.mp4", lay["chunks"] / f"chunk-{i:02d}.key"
        key = chunk_key(html, static)
        parts.append(out)
        if out.is_file() and keyf.is_file() and keyf.read_text().strip() == key:
            reused += 1
            continue
        keyf.unlink(missing_ok=True)
        (hf / "index.html").write_text(html, encoding="utf-8")
        sec = bounds[i + 1] - bounds[i]
        progress(step="chunks", chunk=i + 1, chunks=n, frame=0, frames=round(sec * FPS))
        t0 = time.time()
        render_chunk(hf, out, lay["cache"] / f"chunk-{i:02d}", log,
                     report=lambda f, k, i=i: progress(chunk=i + 1, frame=f, frames=k),
                     on_start=lambda pg: progress(child=pg))  # fmt: skip
        progress(child=None)
        c = check_chunk(out, sec)
        if not c["ok"]:
            out.unlink(missing_ok=True)
            raise VeditError(
                f"{out.name} failed its check: {c}", next=f"see {log}; `vedit render` renders it again"
            )
        keyf.write_text(key + "\n")
        chunk_t.append(round(time.time() - t0, 1))
    t["chunks"] = chunk_t

    t0 = time.time()
    progress(step="join", chunk=n, chunks=n, frame=None, frames=None)
    secs = [b - a for a, b in itertools.pairwise(bounds)]
    tmp = join(parts, secs, lay["master"], lay["work"], log)
    t["join"] = round(time.time() - t0, 1)
    progress(step="verify")
    v = verify(tmp, total)
    if not v["ok"]:
        tmp.unlink(missing_ok=True)
        raise VeditError(f"master failed its check: {v}", next=f"see {log}; then `vedit render` again")
    tmp.replace(lay["master"])
    return {"master": str(lay["master"]), "chunks": n, "reused": reused, "seconds": t, "verify": v}
