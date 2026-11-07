import json
from pathlib import Path

import pytest

from vedit.graphics import faces
from vedit.graphics.faces import FaceTrack, is_cam
from vedit.project import Paths
from vedit.words.timeline import Edl

CAM = [800, 400, 220, 220]  # centre y 510, w 220
BUBBLE = [1500, 40, 120, 120]  # top-right bubble face


def rows(boxes, dt=0.25):
    return [{"t": round(i * dt, 3), "box": b, "cam": False} for i, b in enumerate(boxes)]


def edl():
    return Edl(
        {
            "pieces": [
                {"clip": "A", "in": 10.0, "out": 12.0, "start": 0.0},
                {"clip": "A", "in": 20.0, "out": 22.0, "start": 2.0},
            ],
            "total": 4.0,
        }
    )


def test_cam_rule():
    assert is_cam(CAM)
    assert not is_cam(BUBBLE)
    assert not is_cam([800, 100, 220, 220])  # centre y 210: too high
    assert not is_cam([800, 400, 150, 150])  # too small
    assert not is_cam(None)


def test_at_uses_real_spacing_through_edl():
    # spacing 0.5, not 0.25: source second 10 is row 20, source 20 is row 40
    rs = rows([None] * 100, dt=0.5)
    rs[20]["box"], rs[40]["box"] = CAM, BUBBLE
    tr = FaceTrack({"A": rs}, edl())
    assert tr.at(0.0)["box"] == CAM and tr.at(0.0)["cam"] is True
    assert tr.at(0.0)["t"] == 10.0
    assert tr.at(2.1)["box"] == BUBBLE  # program 2.1 = source 20.1
    assert tr.at(2.1)["cam"] is False


def test_clamping():
    rs = rows([CAM, CAM, None])
    tr = FaceTrack({"A": rs}, Edl({"pieces": [{"clip": "A", "in": 0, "out": 100, "start": 0}], "total": 100}))
    assert tr.at(99)["box"] is None  # past the last row: last row
    assert tr.row("A", -5)["box"] == CAM  # before the first: first row


def test_over_samples_cam_share():
    boxes = [None, CAM, CAM, CAM, BUBBLE, None, None, None]
    tr = FaceTrack(
        {"A": rows(boxes)}, Edl({"pieces": [{"clip": "A", "in": 0, "out": 2, "start": 0}], "total": 2})
    )
    got, cam = tr.over(0.1, 1.1)
    assert got == [CAM, CAM, CAM, BUBBLE] and cam is True
    got, cam = tr.over(1.1, 2.1)
    assert got == [] and cam is False
    assert tr.cam_share(0.1, 1.1) == pytest.approx(0.75)
    s = tr.samples(0.1, 1.1)
    assert [b for _, b in s] == [CAM, CAM, CAM]
    fb = tr.samples(1.1, 2.1)  # no camera-shot face: T's fallback box at the slot middle
    assert fb == [(1.6, [860, 300, 200, 200])]


def make_paths(tmp_path):
    p = Paths(tmp_path)
    (p.media / "proxy").mkdir(parents=True)
    (p.media / "proxy" / "A.mp4").write_bytes(b"fake proxy")
    p.logs.mkdir(parents=True)
    return p


def test_cache_hit_and_force(tmp_path, monkeypatch):
    p = make_paths(tmp_path)
    calls = []

    def fake(proxy, log=None):
        calls.append(proxy)
        return [{"t": 0.0, "box": CAM, "cam": True}, {"t": 0.25, "box": None, "cam": False}]

    monkeypatch.setattr(faces, "sample", fake)
    r1, hit1, k1 = faces.load_clip(p, "A")
    r2, hit2, k2 = faces.load_clip(p, "A")
    assert (hit1, hit2) == (False, True) and k1 == k2 and r1 == r2 and len(calls) == 1
    assert json.loads((p.faces / "A.json").read_text())["key"] == k1
    assert faces.load_clip(p, "A", force=True)[1] is False and len(calls) == 2
    (p.media / "proxy" / "A.mp4").write_bytes(b"another proxy")  # new proxy -> new key
    assert faces.load_clip(p, "A")[1] is False and len(calls) == 3


def test_sample_real_video():
    fx = Path(__file__).parent / "fixtures" / "clip-ar-10s.mp4"
    got = faces.sample(fx)
    assert 38 <= len(got) <= 42
    assert got[1]["t"] - got[0]["t"] == pytest.approx(0.25)
    assert all(set(r) == {"t", "box", "cam"} for r in got)
