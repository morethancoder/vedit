"""Placement on synthetic face rows: side, theme, fit-in-shot, zooms, face checks, big word layout."""

import json

import pytest

from vedit.graphics import place
from vedit.graphics.big import big_layout, text_em
from vedit.words import Edl

CAM_RIGHT = [1100, 300, 300, 300]  # a big camera face right of centre
CAM_LEFT = [400, 300, 300, 300]
BUBBLE = [1650, 40, 120, 120]  # screen layout: small face at the top


class Track:
    """FaceTrack stand-in: a function of program time -> (box, cam)."""

    def __init__(self, fn):
        self.fn = fn

    def at(self, t):
        box, cam = self.fn(t)
        return {"t": t, "box": box, "cam": cam}

    def _ts(self, s, e):
        n = max(2, int((e - s) * 4))
        return [s + (e - s) * (k + 0.5) / n for k in range(n)]

    def over(self, s, e):
        rows = [self.at(t) for t in self._ts(s, e)]
        return [r["box"] for r in rows if r["box"]], sum(r["cam"] for r in rows) / len(rows) > 0.5

    def samples(self, s, e):
        out = [(t, r["box"]) for t in self._ts(s, e) if (r := self.at(t))["box"] and r["cam"]]
        return out or [((s + e) / 2, list(place.FALLBACK_FACE))]

    def cam_share(self, s, e):
        ts = self._ts(s, e)
        return sum(self.at(t)["cam"] for t in ts) / len(ts)


def const(box, cam=True):
    return Track(lambda t: (box, cam))


def flat_lum(mean=0.3, bright=0.1):
    return lambda t, box: (mean, bright)


def test_side_away_from_face():
    assert place.side_for(0, 4, const(CAM_LEFT))[0] == "right"
    assert place.side_for(0, 4, const(CAM_RIGHT))[0] == "left"
    assert place.side_for(0, 4, const(None, False)) == ("left", False)


def test_place_sided_cam_shot_is_dark_without_blur():
    p = place.place_sided("label", 0, 4, const(CAM_RIGHT), [], flat_lum())
    assert (p.side, p.theme, p.blur, p.face_hit) == ("left", "dark", False, 0.0)


def test_place_sided_theme_light_on_bright_background():
    assert place.place_sided("label", 0, 4, const(CAM_RIGHT), [], flat_lum(0.7, 0.2)).theme == "light"
    assert place.place_sided("label", 0, 4, const(CAM_RIGHT), [], flat_lum(0.4, 0.65)).theme == "light"


def test_place_sided_screen_layout_blurs_and_picks_darker_side():
    def lum(t, box):
        return (0.8, 0.7) if box[0] < 900 else (0.2, 0.05)  # left half bright

    p = place.place_sided("label", 0, 4, const(BUBBLE, False), [], lum)
    assert p.blur and not p.cam and p.side == "right" and p.theme == "dark"


def test_place_sided_moves_off_a_face_that_reaches_its_side():
    low = [750, 700, 100, 100]  # centre x 800: the rule says left, but the face zone reaches the left box
    p = place.place_sided("label", 0, 4, const(low), [], flat_lum())
    assert p.side == "right" and p.face_hit == 0.0 and p.notes
    wide = [700, 600, 520, 420]  # centre 960: rule says left, and the left box hits it; right box too
    p = place.place_sided("label", 0, 4, const(wide), [], flat_lum())
    assert p.face_hit > 0 and any("face zone" in n for n in p.notes)


def test_hits_face_applies_zoom():
    box = [1100, 300, 300, 300]
    r = (1500, 300, 1600, 400)  # just right of the zone (ends at 1485) at 1.0
    assert place.hits_face(r, 0, 2, const(box), []) == 0.0
    zooms = [(0.0, 1.5, 960, 540)]  # punch-in pushes the face right
    assert place.hits_face(r, 0, 2, const(box), zooms) == 1.0


def test_fit_in_shot():
    assert place.fit_in_shot(10, 5, [20]) == (10, 5)
    assert place.fit_in_shot(10, 8, [14.5]) == (10, 4.38)  # first stretch long enough
    assert place.fit_in_shot(10, 8, [11]) == (11.1, 6.9)  # else the longest


def test_crossfade_scenes():
    wins = {"a": [10.0, 5.0], "b": [16.0, 4.0], "c": [30.0, 2.0]}
    notes = place.crossfade_scenes(wins, ["a", "b", "c"])
    assert wins["a"] == [10.0, 6.55] and wins["b"] == [16.0, 4.0] and notes == ["a crossfades into b"]


def test_layout_switches_smoothed():
    tr = Track(lambda t: (CAM_RIGHT, True) if t < 10 or t == 12 else (BUBBLE, False))
    assert place.layout_switches(tr, 20) == [10.0]


def test_zoom_plan_resets_off_camera_and_holds():
    edl = Edl(
        {
            "pieces": [
                {"clip": "A", "in": 0, "out": 5, "start": 0},
                {"clip": "A", "in": 6, "out": 11, "start": 5, "zoom": 1.07},
                {"clip": "A", "in": 12, "out": 17, "start": 10, "zoom": 1.07},
                {"clip": "A", "in": 17, "out": 17, "start": 15, "hold": 1.8, "zoom": 1.07},
            ],
            "total": 16.8,
        }
    )
    tr = Track(lambda t: (CAM_RIGHT, True) if t < 10 else (BUBBLE, False))
    z = place.zoom_plan(edl, tr)
    assert [x[1] for x in z] == [1.0, 1.07, 1.0, 1.0]
    assert z[1][2:] == (1250.0, 450.0)  # origin at the face centre


def test_lum_caches_per_program(tmp_path):
    prog = tmp_path / "p.mp4"
    prog.write_bytes(b"x" * 100)
    calls = []

    def grab(t):
        calls.append(t)
        return bytes([200]) * (192 * 108)

    lum = place.Lum(prog, tmp_path / "lum.json", grab=grab)
    assert lum(1.0, (0, 0, 1920, 1080)) == (pytest.approx(0.784, abs=1e-3), 1.0)
    lum(1.0, (0, 0, 960, 540))
    assert calls == [1.0]  # one frame per time
    lum.save()
    lum2 = place.Lum(prog, tmp_path / "lum.json", grab=grab)
    lum2(1.0, (0, 0, 1920, 1080))
    assert calls == [1.0] and json.loads((tmp_path / "lum.json").read_text())
    prog.write_bytes(b"y" * 100)  # a new program invalidates the cache
    place.Lum(prog, tmp_path / "lum.json", grab=grab)(1.0, (0, 0, 1920, 1080))
    assert calls == [1.0, 1.0]


ADV = {"1": 0.6, ".": 0.3, "7": 0.6, "M": 0.9}


def test_big_layout_word_left_of_a_right_face_tucks_one_letter():
    lay = big_layout(0, 5, "1.7M", const(CAM_RIGHT), [], ADV)
    assert lay["side"] == "left"
    assert 110 <= lay["fs"] <= 300
    head_left = CAM_RIGHT[0] - 0.12 * CAM_RIGHT[2]
    right_end = lay["left"] + lay["width"]
    tucked = right_end - head_left
    assert 0 < tucked <= (ADV["M"] - 0.03) * lay["fs"]  # at most the last letter behind the head
    assert lay["left"] >= 0


def test_big_layout_word_right_of_a_left_face():
    lay = big_layout(0, 5, "75K", const(CAM_LEFT), [], {"7": 0.6, "5": 0.6, "K": 0.7})
    assert lay["side"] == "right" and lay["left"] + lay["width"] <= 1920


def test_text_em():
    assert text_em("1.7", ADV, -0.03) == pytest.approx(1.41)


def test_kinetic_column_narrows_beside_the_face():
    face = [764, 172, 383, 383]  # T k-pressure: the zone starts at x 666
    col = place.column("kinetic", "left", 0, 3, const(face), [])
    assert col == 516  # 764 - 0.15*383 - 40 = 666.55, minus the 150 px edge
    p = place.place_sided("kinetic", 0, 3, const(face), [], flat_lum(), width=1977)
    assert p.side == "left" and p.width == col and p.face_hit == 0.0
    assert place.column("kinetic", "left", 0, 3, const([300, 300, 300, 300]), []) == place.KINETIC_MIN


def test_build_plan_fits_places_and_crossfades():
    from vedit.graphics.cues import Cue
    from vedit.graphics.plan import build_plan

    edl = Edl(
        {
            "pieces": [
                {"clip": "A", "in": 0, "out": 10, "start": 0},
                {"clip": "A", "in": 11, "out": 31, "start": 10, "zoom": 1.07},
            ],
            "total": 30,
        }
    )
    cues = [
        Cue("lab", "label", "base", {"title": "t"}, start=8.0, end=14.0),
        Cue("dd1", "doodle", "base", {}, start=15.0, end=20.0),
        Cue("dd2", "doodle", "base", {}, start=20.5, end=24.0),
        Cue("big", "big-number", "base", {"word": "1.7M"}, start=25.0, end=29.0),
    ]
    pl = build_plan(cues, edl, const(CAM_RIGHT), flat_lum(), ADV)
    by = {p.id: p for p in pl.items}
    assert (by["lab"].start, by["lab"].dur) == (10.1, 3.9)  # the join at 10 is a break; the longer stretch
    assert by["lab"].side == "left" and by["lab"].track == 1
    assert by["dd1"].dur == pytest.approx(6.05)  # crossfades into dd2
    assert pl.focus == [(15.0, 24.0)]
    assert by["big"].big["side"] == "left" and by["big"].track == 2
    assert [z[1] for z in pl.zooms] == [1.0, 1.07]
    assert pl.problems() == []


def test_label_and_chip_boxes_use_the_measured_width_flush_to_the_outer_side():
    assert place.box_for("label", "left", width=400, height=220) == (150, 750, 400, 220)
    assert place.box_for("label", "right", width=400, height=220) == (1370, 750, 400, 220)
    assert place.box_for("chip", "right", width=300, height=140)[:2] == (1470, 822)
    from vedit.graphics.plan import chip_size, label_size

    w, h = label_size("1.7", "1", "", {"1": 0.6, ".": 0.3, "7": 0.6})
    assert (w, h) == (round(1.5 * 58 + 72), 170)
    assert label_size("x" * 80, "k", "s", {})[0] == 900 and label_size("t", "k", "s", {})[1] == 220
    assert chip_size("npm i", "l", {})[0] == round(5 * 0.6 * 36 + 60)  # mono: 0.6 em per char
    assert chip_size("مرحبا", "l", {"م": 1.0, "ر": 1.0, "ح": 1.0, "ب": 1.0, "ا": 1.0})[0] == 5 * 40 + 60


def test_a_wide_label_now_touches_a_face_the_fixed_box_missed():
    face = [1000, 700, 200, 200]  # right of centre, low: the 820 px box left of it ends at 970, a wide one
    wide = place.box_for("label", "left", width=900, height=220)
    assert place.hits_face(place.rect(wide), 0, 4, const(face), []) > 0
    narrow = place.box_for("label", "left", width=300, height=220)
    assert place.hits_face(place.rect(narrow), 0, 4, const(face), []) == 0


def test_screen_layout_label_avoids_the_webcam_bubble():
    bubble = [150, 800, 200, 200]  # bottom-left webcam bubble, over the left side's box
    p = place.place_sided("label", 0, 4, const(bubble, False), [], flat_lum(), width=400, height=220)
    assert p.side == "right" and p.face_hit == 0.0 and any("bubble" in n for n in p.notes)
    p = place.place_sided(
        "label", 0, 4, const([1700, 800, 100, 100], False), [], flat_lum(), width=400, height=220
    )
    assert p.side == "left"  # equal brightness: left; the right bubble is avoided


def test_screen_layout_label_reports_a_bubble_touch_when_both_sides_touch():
    both = Track(lambda t: ([150, 800, 200, 200] if t < 2 else [1600, 800, 200, 200], False))
    p = place.place_sided("label", 0, 4, both, [], flat_lum(), width=400, height=220)
    assert p.face_hit > 0 and any("webcam bubble" in n for n in p.notes)


def test_big_word_is_placed_unzoomed_in_the_plan():
    from vedit.graphics.cues import Cue
    from vedit.graphics.plan import build_plan

    edl = Edl({"pieces": [{"clip": "A", "in": 0, "out": 30, "start": 0, "zoom": 1.07}], "total": 30})
    big = [Cue("b", "big-number", "base", {"word": "1.7M"}, start=5.0, end=9.0)]
    zoomed_plan = build_plan(big, edl, const(CAM_RIGHT), flat_lum(), ADV).items[0].big
    flat = big_layout(5, 4, "1.7M", const(CAM_RIGHT), [], ADV)
    assert zoomed_plan == flat


def test_big_word_edge_letter_follows_the_visual_order_of_an_arabic_word():
    adv = {"م": 0.9, "ل": 0.3, "1": 0.6}
    lat = big_layout(0, 5, "1م", const(CAM_RIGHT), [], adv)  # mixed: ltr order, inner = last char "م"
    ar = big_layout(0, 5, "ملم", const(CAM_RIGHT), [], {"م": 0.3, "ل": 0.9})
    ar2 = big_layout(0, 5, "لمم", const(CAM_RIGHT), [], {"م": 0.3, "ل": 0.9})
    # side left: Arabic visual right end is the FIRST char; "ل" (wide) first -> larger tuck letter than "م"
    assert ar2["tuck"] >= 0 and ar["fs"] != ar2["fs"] or ar["left"] != ar2["left"]
    assert lat["side"] == "left"


def test_kinetic_words_squeeze_before_the_exit():
    from vedit.graphics.cues import Cue
    from vedit.graphics.pages import kinetic_times
    from vedit.graphics.plan import Placement, Plan

    c = Cue("k-pressure", "kinetic", "base", {"words": "a b c d"}, start=10.0, end=12.39)
    c.spoken = [10.2, 11.0, 12.1, 12.48]
    p = Placement(c, 10.0, 2.39, 1)
    times, late = kinetic_times(p, 4)
    assert times == [0.2, 1.0, 1.64, 1.64] and late == 2  # limit D - 0.75 = 1.64, order kept
    assert any("2 words squeezed before the exit" in x for x in Plan([p], [], [], [], 20).problems())


def _custom_plan(fields):
    from vedit.graphics.cues import Cue
    from vedit.graphics.plan import build_plan

    edl = Edl({"pieces": [{"clip": "A", "in": 0, "out": 30, "start": 0}], "total": 30})
    c = Cue("cx", "custom", "base", fields, start=5.0, end=9.0)
    return build_plan([c], edl, const(CAM_RIGHT), flat_lum(), ADV)


def test_custom_default_full_frame_warns_about_the_face():
    pl = _custom_plan({"file": "custom/x.html"})
    assert pl.items[0].face_hit == 1.0
    assert any("cx: touches the face" in x for x in pl.problems())


def test_custom_box_away_from_the_face_is_clean_and_ignore_opts_out():
    assert _custom_plan({"file": "f", "box": [100, 100, 400, 300]}).problems() == []
    assert _custom_plan({"file": "f", "box": [1000, 300, 400, 300]}).items[0].face_hit == 1.0
    pl = _custom_plan({"file": "f", "face": "ignore"})
    assert pl.problems() == [] and "face: ignore" in pl.items[0].note()


def test_custom_face_value_is_checked():
    from vedit.report import VeditError

    with pytest.raises(VeditError):
        _custom_plan({"file": "f", "face": "no"})
