import json
from pathlib import Path

import numpy as np
import pytest

from vedit.graphics import cutouts
from vedit.project import Paths

R = {"mt-big-number-1": (9.0, 5.3)}


@pytest.fixture
def setup(tmp_path, monkeypatch):
    paths = Paths(tmp_path)
    (paths.edl).mkdir(parents=True)
    (paths.program).mkdir(parents=True)
    (paths.program / "proxy.mp4").write_bytes(b"x")
    (paths.program / "master.mp4").write_bytes(b"x")
    calls = []

    def fake(src, start, dur, out, scratch, log):
        calls.append((Path(src).name, start, dur, Path(out)))
        out.write_bytes(b"webm")

    monkeypatch.setattr(cutouts, "_make_matte", fake)
    monkeypatch.setattr(
        cutouts, "_studio_matte", lambda src, start, dur, out, log: fake(src, start, dur, out, None, log)
    )
    monkeypatch.setattr(cutouts.studio, "video_cutout_supported", lambda: True)
    return paths, calls


def write_edl(paths, pieces):
    (paths.edl / "edl.json").write_text(json.dumps({"pieces": pieces}))


def test_reuse_then_rebuild_on_range_or_cut(setup):
    paths, calls = setup
    write_edl(paths, [{"clip": "A", "in": 0, "out": 5, "start": 0}])
    r = cutouts.ensure(None, paths, R)
    assert r.rebuilt == ["mt-big-number-1"] and r.reused == [] and len(calls) == 1
    assert r["mt-big-number-1"] == paths.mattes / "mt-big-number-1.webm"
    assert (paths.mattes / "mt-big-number-1.key").exists()
    r = cutouts.ensure(None, paths, R)
    assert r.reused == ["mt-big-number-1"] and len(calls) == 1
    # sub-millisecond jitter is the same range
    cutouts.ensure(None, paths, {"mt-big-number-1": (9.0001, 5.3)})
    assert len(calls) == 1
    cutouts.ensure(None, paths, {"mt-big-number-1": (9.5, 5.3)})
    assert len(calls) == 2
    write_edl(paths, [{"clip": "A", "in": 0, "out": 6, "start": 0}])
    cutouts.ensure(None, paths, {"mt-big-number-1": (9.5, 5.3)})
    assert len(calls) == 3


def test_program_reencode_alone_reuses(setup):
    paths, calls = setup
    write_edl(paths, [{"clip": "A", "in": 0, "out": 5, "start": 0}])
    cutouts.ensure(None, paths, R)
    (paths.program / "proxy.mp4").write_bytes(b"re-encoded, different bytes")
    assert cutouts.ensure(None, paths, R).reused == ["mt-big-number-1"]
    assert len(calls) == 1


def test_variants_use_their_own_source_and_dir(setup):
    paths, calls = setup
    write_edl(paths, [])
    cutouts.ensure(None, paths, R, "proxy")
    r = cutouts.ensure(None, paths, R, "4k")
    assert calls[1][0] == "master.mp4"
    assert r["mt-big-number-1"] == paths.mattes / "4k" / "mt-big-number-1.webm"
    assert len(calls) == 2


def test_missing_output_rebuilds(setup):
    paths, calls = setup
    write_edl(paths, [])
    cutouts.ensure(None, paths, R)
    (paths.mattes / "mt-big-number-1.webm").unlink()
    cutouts.ensure(None, paths, R)
    assert len(calls) == 2


def test_mask_geometry():
    h, w = 540, 960
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    box = [400, 100, 120, 120]  # face
    shelf = np.zeros((h, w), bool)
    shelf[100:300, 700:760] = True  # bookshelf beside the head
    shelf[130:200, 395:405] = (
        True  # touching the ear, inside the tight ellipse edge? (outside tight at x<410)
    )
    m = cutouts.keep_mask(box, shelf, xx, yy)
    assert m[160, 460] > 0.95  # face centre kept
    assert m[400, 460] > 0.95  # body below the chin kept
    assert m[200, 730] < 0.05  # shelf dropped
    assert m[160, 100] < 0.05  # far background dropped
    head, tight, body, chin = cutouts.shapes(box, xx, yy)
    assert chin == 220 and tight.sum() < head.sum()
    assert not body[150, 460]  # no body above the chin


def test_smooth_track_interpolates_missing():
    boxes = [
        np.array([10.0, 10, 100, 100]),
        None,
        np.array([30.0, 10, 100, 100]),
        np.array([30.0, 10, 100, 100]),
    ]
    t = cutouts.smooth_track(boxes)
    assert t.shape == (4, 4) and 10 <= t[1][0] <= 30
    with pytest.raises(Exception, match="no face"):
        cutouts.smooth_track([None, None])


def test_command_lines():
    c = cutouts.cut_cmd(Path("p.mp4"), 9.0, 5.3, Path("o.mp4"))
    assert c[:2] == ["ffmpeg", "-v"] and "h264_videotoolbox" in c and "videotoolbox" in c
    assert c[c.index("-ss") + 1] == "9.000" and c[c.index("-t") + 1] == "5.300"
    r = cutouts.remove_cmd(Path("a.mp4"), Path("b.webm"))
    assert r[:3] == ["npx", "--yes", "hyperframes@0.8.170"] and "remove-background" in r and "best" in r
    e = cutouts.encode_cmd(1920, 1080, "30/1", Path("o.webm"))
    assert "libvpx-vp9" in e and "yuva420p" in e and e[e.index("-s") + 1] == "1920x1080"


def test_make_matte_order(tmp_path, monkeypatch):
    seen = []
    monkeypatch.setattr(cutouts, "run", lambda cmd, t, **kw: seen.append((cmd[0], kw.get("cwd"))))
    monkeypatch.setattr(cutouts, "mask_matte", lambda s, m, o, log=None: o.write_bytes(b"w"))
    out = tmp_path / "o.webm"
    cutouts._make_matte(Path("p.mp4"), 1, 2, out, tmp_path / "scratch", None)
    assert [s[0] for s in seen] == ["ffmpeg", "npx"] and seen[1][1] == tmp_path / "scratch"
    assert out.read_bytes() == b"w" and not out.with_name("o.tmp.webm").exists()


def test_method_switch_rebuilds_and_uses_fallback(setup, monkeypatch):
    paths, _calls = setup
    write_edl(paths, [{"clip": "A", "t0": 0, "t1": 30}])
    cutouts.ensure(None, paths, R)
    used = []
    monkeypatch.setattr(cutouts.studio, "video_cutout_supported", lambda: False)
    monkeypatch.setattr(cutouts, "_make_matte", lambda *a: (used.append("fallback"), a[3].write_bytes(b"w")))
    r = cutouts.ensure(None, paths, R)
    assert r.rebuilt == ["mt-big-number-1"] and used == ["fallback"]
    assert cutouts.method() == cutouts.FALLBACK


def test_studio_matte_writes_via_tmp(tmp_path, monkeypatch):
    seen = []

    def fake(src, start, dur, out, model, **kw):
        seen.append((Path(out).name, model))
        Path(out).write_bytes(b"w")

    monkeypatch.setattr(cutouts.studio, "cutout_video", fake)
    out = tmp_path / "o.webm"
    cutouts._studio_matte(Path("p.mp4"), 1, 2, out, None)
    assert seen == [("o.tmp.webm", "birefnet-lite")] and out.read_bytes() == b"w"
