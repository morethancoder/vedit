import json
from pathlib import Path

import pytest

from vedit.project import Paths
from vedit.render import hf as hfmod
from vedit.render import master
from vedit.report import VeditError


@pytest.fixture
def proj(tmp_path, monkeypatch):
    paths = Paths(tmp_path)
    hf = paths.hf
    for d in ("compositions", "assets", "media", "chunks"):
        (hf / d).mkdir(parents=True)
    (hf / "compositions" / "a.html").write_text("<div>a</div>")
    (hf / "assets" / "gsap.min.js").write_text("gsap")
    (hf / "hyperframes.json").write_text("{}")
    paths.program.mkdir(parents=True)
    paths.mattes.mkdir(parents=True)
    (paths.program / "proxy.mp4").write_bytes(b"p")
    (paths.program / "master.mp4").write_bytes(b"M")
    (hf / "media" / "program.mp4").symlink_to(paths.program / "proxy.mp4")
    (paths.mattes / "mt-x.webm").write_bytes(b"m")
    (hf / "media" / "mt-x.webm").symlink_to(paths.mattes / "mt-x.webm")
    bounds = [0.0, 150.0, 300.5]
    for i in range(2):
        (hf / "chunks" / f"chunk-{i:02d}.html").write_text(f"chunk {i}")
    (hf / "chunks.json").write_text(
        json.dumps({"bounds": bounds, "total": 300.5, "mattes": {"mt-x": [10.0, 5.0]}})
    )
    (paths.edl).mkdir(parents=True)
    (paths.edl / "edl.json").write_text(json.dumps({"pieces": [{"clip": "A"}], "total": 300.5}))
    calls = {"chunks": [], "join": 0}
    k4 = paths.mattes / "4k"
    k4.mkdir()

    def ensure(project, p, ranges, variant, log=None):
        assert variant == "4k" and ranges == {"mt-x": (10.0, 5.0)}
        (k4 / "mt-x.webm").write_bytes(b"m4")
        (k4 / "mt-x.key").write_text("k1\n")
        return {"mt-x": k4 / "mt-x.webm"}

    def render_chunk(hf_dir, out, cache, log, report=None, on_start=None):
        calls["chunks"].append((out.name, (hf_dir / "index.html").read_text()))
        out.write_bytes(b"chunk")

    def join(parts, secs, out, work, log):
        assert secs == [150.0, 150.5]
        calls["join"] += 1
        tmp = out.with_name("master.tmp.mp4")
        tmp.write_bytes(b"master")
        return tmp

    monkeypatch.setattr(master.cutouts, "ensure", ensure)
    monkeypatch.setattr(master, "render_chunk", render_chunk)
    monkeypatch.setattr(master, "join", join)
    monkeypatch.setattr(master, "verify", lambda p, total: {"ok": True, "frames": 18030})
    monkeypatch.setattr(master, "check_chunk", lambda p, sec: {"ok": True})
    from vedit.cut import program

    monkeypatch.setattr(program, "render", lambda edl, p, profile, **kw: {"ok": True})
    return paths, calls


def test_render_then_resume_only_missing_chunk(proj):
    paths, calls = proj
    seen = []
    res = master.render(None, paths, lambda **p: seen.append(p), Path(paths.root / "log"))
    assert [c[0] for c in calls["chunks"]] == ["chunk-00.mp4", "chunk-01.mp4"]
    assert calls["chunks"][1][1] == "chunk 1" and res["reused"] == 0 and calls["join"] == 1
    assert any(p.get("step") == "chunks" and p.get("frames") == 9030 for p in seen)
    assert {"step": "cut-outs", "piece": None, "pieces": None} in seen  # program's piece count is cleared
    # a run killed mid chunk-01: its key never got written
    (paths.vedit / "renders" / "chunks" / "chunk-01.key").unlink()
    calls["chunks"].clear()
    res = master.render(None, paths, lambda **p: None, Path(paths.root / "log"))
    assert [c[0] for c in calls["chunks"]] == ["chunk-01.mp4"] and res["reused"] == 1
    # a changed composition re-renders every chunk
    (paths.hf / "compositions" / "a.html").write_text("<div>b</div>")
    calls["chunks"].clear()
    master.render(None, paths, lambda **p: None, Path(paths.root / "log"))
    assert len(calls["chunks"]) == 2
    # a new 4K program (its render stamp changes) re-renders too
    (paths.program / "master.mp4.stamp.json").write_text(json.dumps({"key": "new"}))
    calls["chunks"].clear()
    master.render(None, paths, lambda **p: None, Path(paths.root / "log"))
    assert len(calls["chunks"]) == 2 and (paths.vedit / "renders" / "master.mp4").read_bytes() == b"master"


def test_bad_chunk_is_not_kept(proj, monkeypatch):
    paths, _ = proj
    monkeypatch.setattr(master, "check_chunk", lambda p, sec: {"ok": False, "frames": 10})
    with pytest.raises(VeditError):
        master.render(None, paths, lambda **p: None, Path(paths.root / "log"))
    ch = paths.vedit / "renders" / "chunks"
    assert not (ch / "chunk-00.mp4").exists() and not (ch / "chunk-00.key").exists()


def test_kill_stale_ignores_unrelated(monkeypatch):
    assert master.kill_stale(None) is False
    assert master.kill_stale({"progress": {"child": 1}}) is False  # pid 1 is launchd, not hyperframes


def test_prepare_points_media_at_4k(proj):
    paths, _ = proj
    lay = master.layout(paths)
    hf = master.prepare(paths, {"mt-x": paths.mattes / "4k" / "mt-x.webm"}, lay)
    assert (hf / "media" / "program.mp4").resolve() == (paths.program / "master.mp4").resolve()
    assert (hf / "media" / "mt-x.webm").resolve() == (paths.mattes / "4k" / "mt-x.webm").resolve()
    assert (hf / "compositions" / "a.html").read_text() == "<div>a</div>"
    assert (hf / "hyperframes.json").is_file()


def test_old_chunks_json_asks_for_build(proj):
    paths, _ = proj
    (paths.hf / "chunks.json").write_text(json.dumps({"bounds": [0, 1]}))
    with pytest.raises(VeditError) as e:
        master.load_chunks(paths)
    assert "vedit build" in e.value.next


def test_disk_need_and_check(proj, monkeypatch):
    paths, _ = proj
    full = master.disk_need(790, 0, 6, False)
    assert 15e9 < full < 30e9
    assert master.disk_need(790, 6, 6, True) < full
    monkeypatch.setattr(master.shutil, "disk_usage", lambda p: type("U", (), {"free": 1e9})())
    with pytest.raises(VeditError) as e:
        master.check_disk(paths, full)
    assert "GB free" in e.value.message


def test_master_render_cmd():
    c = hfmod.render_cmd("hf", "o.mp4", resolution="4k", fps=60, frames_cache_dir="c", video_bitrate="60M",
                         quiet=False)  # fmt: skip
    assert "--video-bitrate" in c and "-q" not in c and c[c.index("--resolution") + 1] == "4k"
    assert "--gpu" in c and "--browser-gpu" in c and "--frames-cache-dir=c" in c and "--quiet" not in c
    assert hfmod.render_env(parallel_stream=True) == {"HF_CAPTURE_PARALLEL_STREAM": "true"}


def test_watch_reads_hf_capture_progress_from_chunk_start(tmp_path):
    import threading
    import time

    log = tmp_path / "l.txt"
    old = "[cutout] frame 340/341\n"  # another tool's counter, before the chunk began
    log.write_text(old)
    start = log.stat().st_size
    with open(log, "a") as f:
        f.write('  ███ 27%  Streaming frame 257/9000\n@hf-progress {"code":"extract_video","pct":10}\n')
        f.write('@hf-progress {"code":"capture","done":264,"total":9000,"pct":27}\n@hf-progress {"code":"cap')
    assert master.capture_progress(old) is None
    got, stop = [], threading.Event()
    th = threading.Thread(
        target=master._watch, args=(log, stop, lambda f, n: got.append((f, n)), start, 0.02)
    )
    th.start()
    time.sleep(0.15)
    with open(log, "a") as f:  # the half-written line completes later
        f.write('ture","done":300,"total":9000,"pct":28}\n')
    time.sleep(0.15)
    stop.set()
    th.join()
    assert got[0] == (264, 9000) and got[-1] == (300, 9000)
    assert all(n == 9000 for _, n in got)  # never the cut-out's 341
