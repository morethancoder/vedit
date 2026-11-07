from pathlib import Path

import pytest

from vedit.words import Edl

DATA = {
    "total": 20.0,
    "fade_start": 19.0,
    "pieces": [
        {"clip": "A", "in": 0.0, "out": 5.0, "start": 0.0},
        {"clip": "A", "in": 8.0, "out": 12.0, "start": 5.0},
        {"clip": "A", "in": 12.0, "out": 12.0, "start": 9.0, "hold": 2.0},
        {"clip": "A", "in": 15.0, "out": 25.0, "start": 11.0},
        {"clip": "A", "in": 25.0, "out": 25.0, "start": 21.0, "hold": 1.0, "sound": "continue"},
    ],
}


def test_g_kept_and_removed():
    e = Edl(DATA)
    assert e.g("A", 2.0) == 2.0
    assert e.g("A", 9.0) == 6.0
    assert e.g("A", 6.0) == 5.0  # removed range -> next kept frame
    assert e.g("A", 13.0) == 11.0
    assert e.g("A", 99.0) == 21.0  # past the end -> last kept end
    assert e.total == 20.0 and e.fade_start == 19.0


def test_src_round_trip_hold_end():
    e = Edl(DATA)
    for t in (0, 2.5, 4.99):
        assert e.src(t) == ("A", t)
        assert e.g(*e.src(t)) == t
    assert e.src(6.0) == ("A", 9.0)
    assert e.src(10.0) == ("A", 12.0)  # inside a hold: its frozen source time
    assert e.src(13.0) == ("A", 17.0)
    assert e.src(500) == ("A", 25.0)


def test_length_joins_holds():
    e = Edl(DATA)
    assert [e.length(p) for p in e.pieces] == [5.0, 4.0, 2.0, 10.0, 1.0]
    assert e.joins() == [5.0, 9.0, 11.0, 21.0]
    assert e.holds() == [(9.0, 2.0)]  # sound: continue is not a chapter


def test_unknown_clip():
    with pytest.raises(ValueError):
        Edl(DATA).g("Z", 1.0)


EDL = Path.home() / "Demos/tele-a7-growth-story/work/edl.json"


@pytest.mark.skipif(not EDL.exists(), reason="T fixture missing")
def test_real_edl_round_trip():
    e = Edl.load(EDL)
    assert e.total > 700 and e.holds()
    n = 0
    for p in e.pieces:
        if "hold" in p:
            continue
        for f in (0.1, 0.5, 0.9):
            t = p["in"] + f * (p["out"] - p["in"])
            if p["out"] - p["in"] < 0.05:
                continue
            assert abs(e.src(e.g("A", t))[1] - t) < 0.01
            n += 1
    assert n > 100
    for k in range(0, int(e.total), 7):
        clip, s = e.src(float(k))
        assert abs(e.g(clip, s) - k) < 0.01 or any(
            "hold" in p and p["start"] <= k < p["start"] + p["hold"] for p in e.pieces
        )
