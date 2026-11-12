from vedit.formats import reframe as rf
from vedit.words.timeline import Edl


class Track:
    """Face centre x as a function of program time; 300 px wide cam face."""

    def __init__(self, cx):
        self.cx = cx

    def at(self, t):
        c = self.cx(t)
        return (
            {"t": t, "box": [c - 150, 200, 300, 300], "cam": True}
            if c is not None
            else {"box": None, "cam": False}
        )


def edl(joins=(), total=20.0):
    starts = [0.0, *joins]
    ends = [*joins, total]
    return Edl({"pieces": [{"clip": "A", "in": s, "out": e, "start": s} for s, e in zip(starts, ends)],
                "total": total})  # fmt: skip


def test_crop_widths():
    assert (
        round(rf.crop_width("9:16"), 1) == 607.5
        and rf.crop_width("4:5") == 864
        and rf.crop_width("16:9") == 1920
    )


def test_still_face_gives_a_still_crop_centred_on_it():
    pts = rf.path(Track(lambda t: 1000 + 10 * ((t * 4) % 2)), edl(), 0, 20, "9:16")
    xs = {p["x"] for p in pts}
    assert len(xs) == 1 and abs(next(iter(xs)) + 607.5 / 2 - 1000) < 15


def test_follows_a_moving_face_and_never_cuts_it():
    pts = rf.path(Track(lambda t: 500 + 60 * t), edl(), 0, 20, "9:16")  # walks 500 -> 1700
    for p in pts:
        c = 500 + 60 * p["t"]
        assert p["x"] <= c - 150 + 0.6 and c + 150 <= p["x"] + 607.5 + 0.6
    assert pts[-1]["x"] > pts[0]["x"] + 900


def test_a_join_is_a_hard_cut():
    pts = rf.path(Track(lambda t: 500 if t < 10 else 1500), edl(joins=(10.0,)), 0, 20, "9:16")
    cut = [p for p in pts if p.get("cut")]
    assert len(cut) == 1 and cut[0]["t"] == 10.0
    assert rf.x_at(pts, 9.99) < 400 and rf.x_at(pts, 10.0) > 1100


def test_crop_stays_inside_the_frame_and_handles_no_face():
    pts = rf.path(Track(lambda t: 30), edl(), 0, 5, "9:16")
    assert all(p["x"] == 0 for p in pts)
    pts = rf.path(Track(lambda t: None), edl(), 0, 5, "1:1")
    assert all(abs(p["x"] - (1920 - 1080) / 2) < 1 for p in pts)


def test_16x9_needs_no_crop():
    assert {p["x"] for p in rf.path(Track(lambda t: 300), edl(), 0, 5, "16:9")} == {0.0}


def test_recentres_fully_after_the_speaker_moves():
    """A step move: the crop doesn't stop at the dead-zone edge, it settles with the face in the middle."""
    pts = rf.path(Track(lambda t: 900 if t < 5 else 1020), edl(), 0, 20, "9:16")
    assert abs(rf.x_at(pts, 2) + 607.5 / 2 - 900) < 8
    assert abs(rf.x_at(pts, 18) + 607.5 / 2 - 1020) < 0.03 * 607.5


def test_a_piece_starts_centred_on_its_median_face_not_its_first_sample():
    pts = rf.path(Track(lambda t: 600 if t < 0.3 else 1000), edl(), 0, 20, "9:16")
    assert (
        abs(rf.x_at(pts, 1.0) + 607.5 / 2 - 1000) < 8
    )  # (at t=0 the crop still keeps the real face in frame)
