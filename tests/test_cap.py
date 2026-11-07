import json
from pathlib import Path

import pytest

from vedit.ingest import cap as capmod
from vedit.ingest.cap import CapError, Segment, find_cap_for_export, find_export, read_cap, segment_filter

REAL = capmod.CAP_RECORDINGS / "Built-in Retina Display (Area) 2026-11-03 10.31 AM (1).cap"
REAL_EXPORT = capmod.CAP_RECORDINGS / "how i grew a telegram channel.mp4"
FILTER = Path.home() / "Demos/tele-a7-growth-story/work/A-cam.filter"


def make_cap(root, name, pretty="Cap X", segs=None, result=b"", cams=1, timescale=1.0, mirror=False):
    c = root / f"{name}.cap"
    (c / "output").mkdir(parents=True)
    rec = []
    for i in range(cams):
        (c / f"content/segments/segment-{i}").mkdir(parents=True)
        (c / f"content/segments/segment-{i}/camera.mp4").write_bytes(b"x")
        rec.append({"display": {"path": f"content/segments/segment-{i}/display.mp4", "fps": 30},
                    "camera": {"path": f"content/segments/segment-{i}/camera.mp4", "fps": 25}})  # fmt: skip
    (c / "recording-meta.json").write_text(json.dumps({"pretty_name": pretty, "segments": rec}))
    segs = segs or [{"recordingSegment": 0, "start": 0.0, "end": 2.0}]
    segs = [{"timescale": timescale, **s} for s in segs]
    cfg = {"timeline": {"segments": segs}, "camera": {"mirror": mirror}}
    (c / "project-config.json").write_text(json.dumps(cfg))
    if result is not None:
        (c / "output" / "result.mp4").write_bytes(result)
    return c


def test_read_basic(tmp_path):
    c = make_cap(tmp_path, "a", pretty="My Cap", mirror=True)
    p = read_cap(c / "output")  # any path inside
    assert p.pretty_name == "My Cap" and p.mirror and p.camera_fps == 25
    assert p.camera.name == "camera.mp4" and p.duration == 2.0
    assert p.export == c.resolve() / "output" / "result.mp4"


def test_timescale_unsupported(tmp_path):
    c = make_cap(tmp_path, "a", timescale=2.0)
    with pytest.raises(CapError, match="timescale"):
        read_cap(c)


def test_missing_and_no_camera(tmp_path):
    c = make_cap(tmp_path, "a")
    (c / "project-config.json").unlink()
    with pytest.raises(CapError, match="project-config.json"):
        read_cap(c)
    d = make_cap(tmp_path, "b")
    (d / "recording-meta.json").write_text(json.dumps({"segments": [{"display": {}}]}))
    with pytest.raises(CapError, match="no camera"):
        read_cap(d)


def test_multi_segment_filter():
    segs = [Segment(0, 0.0, 1.0), Segment(1, 2.0, 3.5)]
    f = segment_filter(segs, 25)
    assert f == (
        "[0:v]trim=start_frame=0:end_frame=25,setpts=PTS-STARTPTS[v0];"
        "[1:v]trim=start_frame=50:end_frame=87,setpts=PTS-STARTPTS[v1];[v0][v1]concat=n=2:v=1:a=0[v]"
    )


def test_find_export_by_name(tmp_path):
    c = make_cap(tmp_path, "a", pretty="Cap Y", result=None)
    (tmp_path / "ex").mkdir()
    (tmp_path / "ex" / "Cap Y.mov").write_bytes(b"1")
    assert find_export(read_cap(c, search=()), search=[tmp_path / "ex"]).name == "Cap Y.mov"
    assert find_export(read_cap(c, search=()), search=[tmp_path / "n*"]) is None


def test_match_by_pretty_name(tmp_path):
    make_cap(tmp_path, "a", pretty="other", result=b"1")
    b = make_cap(tmp_path, "b", pretty="my video", result=b"2")
    ex = tmp_path / "out" / "my video.mp4"
    ex.parent.mkdir()
    ex.write_bytes(b"zzz")
    assert find_cap_for_export(ex, roots=[tmp_path]) == b


def test_match_by_size(tmp_path):
    make_cap(tmp_path, "a", result=b"1234")
    b = make_cap(tmp_path, "b", result=b"12345")
    ex = tmp_path / "renamed.mp4"
    ex.write_bytes(b"abcde")
    assert find_cap_for_export(ex, roots=[tmp_path]) == b


def test_ambiguous_and_none(tmp_path):
    make_cap(tmp_path, "a", result=b"12345")
    make_cap(tmp_path, "b", result=b"12345")
    ex = tmp_path / "r.mp4"
    ex.write_bytes(b"abcde")
    with pytest.raises(CapError, match="several"):
        find_cap_for_export(ex, roots=[tmp_path])
    ex.write_bytes(b"abc")
    monkey = capmod.ffprobe_duration
    capmod.ffprobe_duration = lambda p: 99.0
    try:
        with pytest.raises(CapError, match="no .cap matches"):
            find_cap_for_export(ex, roots=[tmp_path])
    finally:
        capmod.ffprobe_duration = monkey


def test_match_by_duration(tmp_path, monkeypatch):
    make_cap(tmp_path, "a", result=None)
    b = make_cap(tmp_path, "b", result=None, segs=[{"recordingSegment": 0, "start": 0.0, "end": 5.0}])
    ex = tmp_path / "r.mp4"
    ex.write_bytes(b"abc")
    monkeypatch.setattr(capmod, "ffprobe_duration", lambda p: 5.05)
    assert find_cap_for_export(ex, roots=[tmp_path]) == b


real = pytest.mark.skipif(not REAL.exists(), reason="real Cap fixture missing")


@real
def test_real_read():
    p = read_cap(REAL)
    assert p.pretty_name == "Cap 2026-11-03 at 10.47.40" and p.camera_fps == 25
    assert len(p.segments) == 6 and p.mirror is False
    assert p.export.stat().st_size == 2270464217


@real
@pytest.mark.skipif(not FILTER.exists(), reason="T filter missing")
def test_real_filter():
    assert segment_filter(read_cap(REAL).segments, 25) == FILTER.read_text().strip()


@real
@pytest.mark.skipif(not REAL_EXPORT.exists(), reason="real export missing")
def test_real_match():
    assert find_cap_for_export(REAL_EXPORT) == REAL
