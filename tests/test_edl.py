import itertools
import json

import numpy as np

from vedit.cut import edl
from vedit.cut.cutsfile import WordCut
from vedit.words import Edl

DUR = 20.0


def env(quiet=(), loud=-10.0):
    """10 ms envelope over DUR: loud everywhere except the (a, b) ranges in `quiet` (-60 dB)."""
    db = np.full(int(DUR * 100), loud)
    for a, b in quiet:
        db[int(a * 100) : int(b * 100)] = -60.0
    return db


def words(n=18):
    return [{"t0": float(i), "t1": i + 0.8, "w": f"w{i}"} for i in range(n)]


def phrase(i0, i1, w, pin=None, kind="phrase"):
    return WordCut("A", kind, f"p{i0}", "", i0, i1, w[i0]["t0"], w[i1 + 1]["t0"], pin, f"A {w[i0]['t0']}")


def build(cuts, db, w=None, **kw):
    w = w or words()
    return edl.build(cuts, kw.pop("refined", {}), {"A": db}, {"A": w}, {"A": DUR}, **kw)


def test_boundaries_snap_to_quietest_within_reach():
    w = words()
    db = env(
        [(4.05, 4.07), (6.9, 6.92)]
    )  # quiet spots 0.05 before word 4 and 0.1 before the cut end (word 7)
    data, _ = build([phrase(4, 6, w)], db, w)
    ps = data["pieces"]
    cut_at = [(a["out"], b["in"]) for a, b in itertools.pairwise(ps)]
    assert any(abs(a - 4.07) < 0.04 and abs(b - 6.92) < 0.04 for a, b in cut_at), cut_at


def test_priority_pin_then_refined_then_snap():
    w = words()
    c = phrase(4, 6, w)
    r = {c.key: {"in": 5.0, "out": 6.0}}
    data, _ = build([c], env(), w, refined=r)
    ps = data["pieces"]
    assert ps[0]["out"] == 5.0 and ps[1]["in"] == 6.0
    c.pin = (9.0, 10.0)
    data, info = build([c], env(), w, refined=r)
    assert data["pieces"][0]["out"] == 9.0 and data["pieces"][1]["in"] == 10.0
    assert info["pins"] == 1


def test_long_pause_becomes_keep_split_around_the_cut():
    data, info = build([], env([(5.0, 6.0)]))
    ps = data["pieces"]
    assert info["pauses"] == 1 and len(ps) == 2
    assert abs(ps[0]["out"] - 5.15) < 0.04 and abs(ps[1]["in"] - 5.85) < 0.04
    assert abs(data["total"] - (DUR - 0.7)) < 0.1


def test_short_pause_stays_and_grid_and_min_piece():
    data, _ = build([], env([(5.0, 5.4)]))
    assert len(data["pieces"]) == 1
    data, _ = build([phrase(4, 6, words())], env(), refined={})
    for p in data["pieces"]:
        assert abs(p["in"] * 30 - round(p["in"] * 30)) < 2e-3 and p["out"] - p["in"] >= 0.2


def test_opening_rule_drops_the_breath_before_first_word():
    cut = WordCut("A", "pin", "x", "", None, None, 0.5, 1.0, (0.5, 1.0), "A 0.5")
    data, _ = build([cut], env())
    assert data["pieces"][0]["in"] == 0.0  # 0-0.5 ends after 0.4: kept
    cut = WordCut("A", "pin", "x", "", None, None, 0.3, 1.0, (0.3, 1.0), "A 0.3")
    data, _ = build([cut], env())
    assert data["pieces"][0]["in"] == 1.0  # 0-0.3 ends before 0.4: dropped


def test_end_last_word_tail_and_fade_start():
    w = words(10)
    data, _ = build([], env(), w, end="last-word")
    last = w[-1]["t1"]
    assert abs(data["pieces"][-1]["out"] - round((last + edl.TAIL) * 30) / 30) < 0.01
    assert data["fade_start"] == round(last, 4)
    data, _ = build([], env(), w, end=None)
    assert data["fade_start"] is None and data["pieces"][-1]["out"] == DUR


def test_chapter_hold_at_quietest_and_in_program_clock(tmp_path):
    db = env([(8.1, 8.12)])
    data, info = build([], db, chapters=[("A", 8.0, 1.8)])
    ps = data["pieces"]
    h = [p for p in ps if "hold" in p]
    assert info["holds"] == 1 and h[0]["hold"] == 1.8 and abs(h[0]["in"] - 8.1) < 0.04
    assert abs(data["total"] - (DUR + 1.8)) < 0.01
    f = tmp_path / "edl.json"
    f.write_text(json.dumps(data))
    e = Edl.load(f)
    assert len(e.holds()) == 1 and abs(e.g("A", 9.0) - 9.0 - 1.8) < 0.05


def test_hold_in_removed_pause_goes_after_previous_piece():
    data, _ = build([], env([(5.0, 7.0)]), chapters=[("A", 6.0, 1.8)])
    ps = data["pieces"]
    k = next(i for i, p in enumerate(ps) if "hold" in p)
    assert abs(ps[k - 1]["out"] - 5.15) < 0.04


def test_zoom_alternates_on_camera_jump_cuts_only():
    w = words()
    cuts = [phrase(2, 2, w), phrase(5, 5, w), phrase(8, 8, w), phrase(11, 11, w)]
    data, info = build(cuts, env(), w, zoom_clips={"A"})
    z = [p.get("zoom", 1.0) for p in data["pieces"]]
    assert z[0] == 1.0 and z[1:] == [1.07, 1.0, 1.07, 1.0][: len(z) - 1] and info["zoomed"] == 2
    data, info = build(cuts, env(), w)  # a plain screen source never zooms
    assert not any("zoom" in p for p in data["pieces"]) and info["zoomed"] == 0


def test_zoom_skips_short_pieces_and_holds_and_resets():
    w = words()
    data, _ = build(
        [phrase(2, 2, w), phrase(4, 4, w)], env(), w, chapters=[("A", 8.0, 1.8)], zoom_clips={"A"}
    )
    for k, p in enumerate(data["pieces"]):
        if "hold" in p or k == 0:
            assert "zoom" not in p
        if k and "hold" in data["pieces"][k - 1]:
            assert "zoom" not in p
    pieces = [
        {"clip": "A", "in": 0, "out": 5},
        {"clip": "A", "in": 6, "out": 6.5},
        {"clip": "A", "in": 7, "out": 12},
    ]
    assert edl.zoom_pieces(pieces, {"A"}) == 1 and "zoom" not in pieces[1]  # short piece resets
    assert pieces[2].get("zoom") == 1.07
