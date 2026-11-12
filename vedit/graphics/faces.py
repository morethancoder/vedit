"""Face track: where his face is every quarter second, so graphics keep off it.

Each source clip's 1080p proxy (`.vedit/media/proxy/<clip>.mp4`) is sampled at 4 fps with OpenCV Haar
(frontal face, largest one wins). Boxes are `[x, y, w, h]` in 1920x1080 px. Ingest already bakes the source's
camera mirror into the A-cam and the proxy, so boxes are in display coordinates; the cache key hashes the
proxy file, so a different mirror state (a rebuilt proxy) is a different key.

`cam` marks a camera shot: a face low (centre y > 260) and large (w > 170); the screen layout's bubble
face sits at the top. Rows are indexed by the real sample spacing, not by 0.25.
Ported from T tools/faces.py + tools/build.py (face_at, faces_over, face_samples).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import numpy as np

from vedit.project import Paths
from vedit.report import VeditError
from vedit.run import DECODE, FF, RunError, _timeout_bin, frame_grab, hash_of, sample_hash
from vedit.words.timeline import Edl

FPS = 4
W, H = 960, 540  # detection size; boxes are doubled to 1920x1080
PARAMS = {
    "fps": FPS,
    "w": W,
    "h": H,
    "scale": 1.1,
    "neighbors": 6,
    "min": 28,
    "cam_y": 260,
    "cam_w": 170,
    "v": 1,
}
FALLBACK = [860, 300, 200, 200]  # T: used when no camera-shot face is in a slot
SAMPLE_TIMEOUT = 1800
FACE_TIMEOUT = 120


def is_cam(box) -> bool:
    """Camera shot = face low and large; the screen layout's bubble face is at the top."""
    return bool(box and box[1] + box[3] / 2 > 260 and box[2] > 170)


def detect(frames) -> list:
    """Largest Haar face per gray 960x540 frame (iterable of arrays) -> [x,y,w,h] in 1080p or None."""
    import cv2

    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    out = []
    for g in frames:
        faces = cascade.detectMultiScale(g, scaleFactor=1.1, minNeighbors=6, minSize=(28, 28))
        if len(faces):
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            out.append([int(x * 2), int(y * 2), int(w * 2), int(h * 2)])
        else:
            out.append(None)
    return out


def _frames(proxy: Path, log: Path | None):
    """Yield gray frames at 4 fps: VideoToolbox decode, raw gray pipe, time-boxed, stdin closed."""
    cmd = [
        *FF,
        *DECODE,
        "-i",
        str(proxy),
        "-vf",
        f"fps={FPS},scale={W}:{H},format=gray",
        "-f",
        "rawvideo",
        "-",
    ]
    tbin = _timeout_bin()
    cmd = [tbin, str(SAMPLE_TIMEOUT), "nice", "-n", "19", *cmd] if tbin else ["nice", "-n", "19", *cmd]
    errf = open(log, "ab") if log else subprocess.DEVNULL  # noqa: SIM115
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=errf)
    n = W * H
    try:
        while True:
            buf = proc.stdout.read(n)
            if len(buf) < n:
                break
            yield np.frombuffer(buf, np.uint8).reshape(H, W)
    finally:
        proc.stdout.close()
        proc.wait()
        if log:
            errf.close()
    if proc.returncode != 0:
        raise RunError(
            f"ffmpeg sampling {proxy.name} failed: exit {proc.returncode} (see .vedit/logs/faces.log)"
        )


def sample(proxy: Path, log: Path | None = None) -> list[dict]:
    """Rows `{t, box, cam}` for one proxy; t from the real sample spacing (duration / frames)."""
    boxes = detect(_frames(proxy, log))
    if not boxes:
        return []
    dt = 1 / FPS
    return [{"t": round(i * dt, 3), "box": b, "cam": is_cam(b)} for i, b in enumerate(boxes)]


def proxy_of(paths: Paths, clip: str) -> Path:
    return paths.media / "proxy" / f"{clip}.mp4"


def load_clip(
    paths: Paths, clip: str, force: bool = False, save: bool = True
) -> tuple[list[dict], bool, str]:
    """(rows, cache_hit, key) for one clip; cached at .vedit/faces/<clip>.json (save=False: nothing written)."""
    proxy = proxy_of(paths, clip)
    fp = sample_hash(proxy)
    if fp is None:
        raise VeditError(f"missing {proxy}", next="vedit new <input>  (rebuilds media)")
    key = hash_of(PARAMS, fp)
    f = paths.faces / f"{clip}.json"
    if not force and f.is_file():
        try:
            d = json.loads(f.read_text())
            if d.get("key") == key:
                return d["rows"], True, key
        except (ValueError, KeyError):
            pass
    rows = sample(proxy, paths.logs / "faces.log" if save else None)
    if save:
        paths.faces.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"key": key, "rows": rows}))
    return rows, False, key


class FaceTrack:
    """Face rows for every clip, looked up by program time through the EDL."""

    def __init__(self, rows: dict[str, list[dict]], edl: Edl | None = None):
        self.rows = rows
        self.edl = edl
        for rs in rows.values():  # always re-derive cam so a rule change never needs a re-sample
            for r in rs:
                r["cam"] = is_cam(r["box"])

    @classmethod
    def load(cls, paths: Paths, clips, edl: Edl | None = None, force: bool = False, save: bool = True):
        return cls({c: load_clip(paths, c, force, save)[0] for c in clips}, edl)

    def row(self, clip: str, st: float) -> dict:
        rows = self.rows[clip]
        dt = (rows[1]["t"] - rows[0]["t"]) if len(rows) > 1 else 1 / FPS
        return rows[min(len(rows) - 1, max(0, round(st / dt)))]

    def at(self, t: float) -> dict:
        """Row at program time t: `{t, box, cam}` (clamped to the clip's ends)."""
        clip, st = self.edl.src(t)
        return self.row(clip, st)

    def over(self, s: float, e: float) -> tuple[list[list[int]], bool]:
        """(boxes seen in [s, e], camera-shot share > 0.5), 4 samples per second."""
        boxes, cams = [], 0
        n = max(2, int((e - s) * 4))
        for k in range(n):
            r = self.at(s + (e - s) * (k + 0.5) / n)
            if r["box"]:
                boxes.append(r["box"])
            cams += r["cam"]
        return boxes, cams / n > 0.5

    def samples(self, s: float, e: float) -> list[tuple[float, list[int]]]:
        """(t, box) of the camera-shot face over a slot, 4 per second; a default box when none."""
        out, n = [], max(2, int((e - s) * 4))
        for k in range(n):
            t = s + (e - s) * (k + 0.5) / n
            r = self.at(t)
            if r["box"] and r["cam"]:
                out.append((t, r["box"]))
        return out or [((s + e) / 2, list(FALLBACK))]

    def cam_share(self, s: float, e: float) -> float:
        n = max(2, int((e - s) * 4))
        return sum(self.at(s + (e - s) * (k + 0.5) / n)["cam"] for k in range(n)) / n


def sheet(track: FaceTrack, paths: Paths, start: float = 0.0, end: float | None = None, grid=(4, 4)) -> Path:
    """Contact sheet of frames spread over [start, end] with each sample's box: green = cam, orange = a
    face that is not a camera shot, red label "no face". Written to .vedit/faces/sheet.jpg."""
    import cv2

    end = track.edl.total if end is None else end
    cols, rows_n = grid
    n = cols * rows_n
    tmp = paths.faces / "sheet-frames"
    tmp.mkdir(parents=True, exist_ok=True)
    tiles = []
    for k in range(n):
        t = start + (end - start) * (k + 0.5) / n
        clip, st = track.edl.src(t)
        row = track.row(clip, st)
        jpg = frame_grab(proxy_of(paths, clip), st, tmp / f"{k:02d}.jpg", timeout=FACE_TIMEOUT)
        img = cv2.imread(str(jpg))
        if img is None:
            img = np.zeros((1080, 1920, 3), np.uint8)
        img = cv2.resize(img, (1920, 1080))
        b = row["box"]
        if b:
            col = (0, 200, 0) if row["cam"] else (0, 140, 255)
            cv2.rectangle(img, (b[0], b[1]), (b[0] + b[2], b[1] + b[3]), col, 8)
        label = f"{t:.1f}s {clip} " + ("cam" if b and row["cam"] else "face" if b else "no face")
        cv2.putText(
            img, label, (30, 90), cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 255) if not b else (255, 255, 255), 8
        )
        tiles.append(cv2.resize(img, (480, 270)))
    grid_img = np.vstack([np.hstack(tiles[r * cols : (r + 1) * cols]) for r in range(rows_n)])
    out = paths.faces / "sheet.jpg"
    cv2.imwrite(str(out), grid_img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    shutil.rmtree(tmp, ignore_errors=True)
    return out
