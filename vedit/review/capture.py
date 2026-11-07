"""Snapshots of the built `.vedit/hf/` project with text boxes and tween timings measured in the page.

Why a probe and not `hyperframes snapshot` alone: snapshot only writes PNGs, and `inspect`/`check` report
issues, not boxes. Reaching into HyperFrames' bundled puppeteer would tie vedit to its private file layout.
So review renders a copy of the project, `.vedit/review/hf/` (compositions and assets copied, media
symlinked to the same files, `.vedit/hf/` itself is never touched), whose index.html gets one extra script,
`probe.js`. The probe wraps the player's seek; after each seek HyperFrames makes, it measures every visible
graphic (text node boxes via Range rects, rendered px = computed font size x the element's on-screen scale,
computed colour, opacity chain) and, once, every graphic's GSAP tweens. It posts them with a synchronous
XHR to a one-shot receiver vedit runs on 127.0.0.1 (stdlib http.server), so each measurement lands
before the screenshot of that same seek. Nothing new to install: it runs in the browser snapshot already uses.

Two snapshot runs: one frame to read the tweens (peaks come from them, flags.peak_of), then one run with
every peak. Both are cached in `.vedit/review/cache/` under the content hash of the hf project files (media
by a size + head/tail sample), the pinned HyperFrames and the probe itself.
"""

from __future__ import annotations

import http.server
import json
import os
import re
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path

from vedit.graphics.compose import copy_if_changed
from vedit.report import VeditError
from vedit.run import hash_of, sample_hash
from vedit.run import run as sh
from vedit.versions import HYPERFRAMES

PROBE = Path(__file__).with_name("probe.js")
SNAP_BASE, SNAP_PER_SHOT = 180, 15  # s: snapshot time box = base + per frame
SKIP = {".hyperframes", "index.html"}


@dataclass
class Host:
    id: str
    start: float
    dur: float
    track: int


@dataclass
class Capture:
    hosts: list[Host]
    timelines: dict[str, dict]  # id -> {dur, tweens}
    peaks: dict[str, float]  # id -> program second
    texts: dict[str, list[dict]]  # id -> texts measured at its peak (missing: not measured)
    shots: dict[str, Path]  # id -> PNG at its peak
    zooms: list[tuple[float, float, float, float]]  # (t, scale, ox, oy)
    cache_hit: bool
    key: str


# ---- reading the built project ----

_HOST = re.compile(r"<div [^>]*data-composition-src=\"compositions/[^\"]+\"[^>]*>")
_ATTR = re.compile(r'([\w-]+)="([^"]*)"')
_ZOOM = re.compile(
    r'tl\.set\("#cam", \{ scale: ([\d.]+), transformOrigin: "(-?[\d.]+)px (-?[\d.]+)px" \}, ([\d.]+)\);'
)


def hosts_of(index_html: str) -> list[Host]:
    """Graphic hosts of the root composition (compose.host), in time order."""
    out = []
    for m in _HOST.finditer(index_html):
        a = dict(_ATTR.findall(m.group(0)))
        out.append(
            Host(a["id"], float(a["data-start"]), float(a["data-duration"]), int(a["data-track-index"]))
        )
    return sorted(out, key=lambda h: (h.start, h.id))


def zooms_of(index_html: str) -> list[tuple[float, float, float, float]]:
    """Punch-ins `(t, scale, ox, oy)` the root timeline sets on #cam, in time order."""
    rows = [(float(t), float(z), float(ox), float(oy)) for z, ox, oy, t in _ZOOM.findall(index_html)]
    return sorted(rows)


def zoom_at(zooms, t: float) -> tuple[float, float, float] | None:
    cur = None
    for t0, z, ox, oy in zooms:
        if t0 <= t + 1e-6:
            cur = (z, ox, oy)
    return cur


def files_key(hf: Path) -> str:
    """Content hash of the hf project (media and symlinks by sample), the HyperFrames pin and the probe."""
    parts: list = [HYPERFRAMES, PROBE]
    for f in sorted(p for p in hf.rglob("*") if p.is_file() and ".hyperframes" not in p.parts):
        big = f.is_symlink() or f.suffix in (".mp4", ".webm", ".mov")
        parts += [str(f.relative_to(hf)), sample_hash(f) if big else f]
    return hash_of(*parts)


# ---- the review copy ----


def mirror(hf: Path, dst: Path, sink: str) -> None:
    """`dst` = the hf project with the probe in index.html. Small files copied, symlinks re-pointed at the
    same targets (absolute, so they survive the move one folder down)."""
    if dst.exists():
        shutil.rmtree(dst)
    for src in sorted(hf.rglob("*")):
        rel = src.relative_to(hf)
        if rel.parts[0] in SKIP:
            continue
        out = dst / rel
        if src.is_symlink():
            out.parent.mkdir(parents=True, exist_ok=True)
            out.symlink_to(os.path.realpath(src))
        elif src.is_file():
            copy_if_changed(src, out)
    probe = PROBE.read_text(encoding="utf-8").replace("__VEDIT_SINK__", sink)
    html = (hf / "index.html").read_text(encoding="utf-8")
    tag = f"<script>\n{probe}\n</script>\n</body>"
    (dst / "index.html").write_text(html.replace("</body>", tag, 1), encoding="utf-8")


class Receiver:
    """One-shot local HTTP sink for the probe's JSON posts (127.0.0.1, a free port)."""

    def __init__(self):
        got: list[dict] = []

        class H(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                n = int(self.headers.get("Content-Length") or 0)
                try:
                    got.append(json.loads(self.rfile.read(n).decode("utf-8")))
                except ValueError:
                    pass
                self.send_response(204)
                self._cors()

            def do_OPTIONS(self):
                self.send_response(204)
                self._cors()

            def _cors(self):
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Headers", "*")
                self.send_header("Access-Control-Allow-Private-Network", "true")
                self.end_headers()

            def log_message(self, *a):
                pass

        self.got = got
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}/"

    def __enter__(self):
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self.srv.shutdown()
        self.srv.server_close()


# ---- snapshots ----


def hf_snapshot(proj: Path, times: list[float], out: Path, log: Path) -> dict[float, Path]:
    """`hyperframes snapshot` at exact seconds; returns second -> PNG."""
    out.mkdir(parents=True, exist_ok=True)
    at = ",".join(f"{t:g}" for t in times)
    cmd = ["npx", "--yes", f"hyperframes@{HYPERFRAMES}", "snapshot", str(proj), "--at", at, "--no-end"]
    cmd += ["--keep", "--output", str(out), "--describe", "false"]
    sh(cmd, SNAP_BASE + SNAP_PER_SHOT * len(times), cwd=proj, log=log)
    got = {}
    for f in out.glob("at-*s.png"):
        try:
            got[float(f.stem[3:-1])] = f
        except ValueError:
            continue
    return got


def distinct(times: list[float]) -> list[float]:
    """Seconds rounded to ms, nudged apart so no two share a snapshot file name (1 ms rule)."""
    out, used = [], set()
    for t in times:
        ms = round(t * 1000)
        while ms in used:
            ms += 2
        used.add(ms)
        out.append(ms / 1000)
    return out


def _near(d: dict[float, object], t: float, tol: float = 0.0015):
    k = min(d, key=lambda s: abs(s - t), default=None)
    return d[k] if k is not None and abs(k - t) <= tol else None


def capture(hf: Path, review: Path, log: Path, force: bool = False) -> Capture:
    """Measure + snapshot every graphic of the built project at its peak (cached by files_key)."""
    from vedit.review.flags import peak_of

    index = hf / "index.html"
    if not index.is_file():
        raise VeditError(f"{index} is not built yet", next="vedit build")
    html = index.read_text(encoding="utf-8")
    hosts, zooms = hosts_of(html), zooms_of(html)
    if not hosts:
        raise VeditError("the build has no graphics to review", next="write cues.yaml, then: vedit build")
    key = files_key(hf)
    cache = review / "cache"
    kf = cache / "key.json"
    if not force and kf.is_file():
        try:
            d = json.loads(kf.read_text())
        except ValueError:
            d = {}
        shots = {i: cache / "shots" / f for i, f in (d.get("shots") or {}).items()}
        if d.get("key") == key and shots and all(f.is_file() for f in shots.values()):
            return Capture(hosts, d["timelines"], d["peaks"], d["texts"], shots, zooms, True, key)
    if cache.exists():
        shutil.rmtree(cache)
    proj = review / "hf"
    with Receiver() as rx:
        mirror(hf, proj, rx.url)
        hf_snapshot(proj, [0.0], cache / "first", log)
        timelines = next((m["timelines"] for m in rx.got if m.get("timelines")), None)
        if not timelines:
            raise VeditError(f"the review probe sent nothing back (HyperFrames {HYPERFRAMES}); see {log}")
        want = []
        for h in hosts:
            tl = timelines.get(h.id) or {}
            want.append(h.start + peak_of(tl.get("tweens") or [], h.dur))
        times = distinct(want)
        peaks = {h.id: t for h, t in zip(hosts, times, strict=True)}
        rx.got.clear()
        pngs = hf_snapshot(proj, times, cache / "shots", log)
        by_t = {float(m["t"]): m.get("hosts") or {} for m in rx.got if "t" in m}
    shutil.rmtree(cache / "first", ignore_errors=True)
    texts, shots = {}, {}
    for h in hosts:
        t = peaks[h.id]
        png = _near(pngs, t)
        if png is not None:
            shots[h.id] = png
        seen = _near(by_t, t)
        if seen is not None:
            texts[h.id] = seen.get(h.id, [])
    if not shots:
        raise VeditError(f"hyperframes snapshot wrote no frames; see {log}")
    rec = {
        "key": key,
        "timelines": timelines,
        "peaks": peaks,
        "texts": texts,
        "shots": {i: f.name for i, f in shots.items()},
    }
    kf.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
    return Capture(hosts, timelines, peaks, texts, shots, zooms, False, key)
