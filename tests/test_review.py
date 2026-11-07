import numpy as np
import pytest

from vedit.review import flags as fl
from vedit.review.capture import distinct, hosts_of, zoom_at, zooms_of
from vedit.review.sheet import where


def tw(s, d, keys, opacity=None, ease="power2.out"):
    return {"s": s, "d": d, "keys": keys, "opacity": opacity, "ease": ease}


LABEL = [
    tw(0.08, 0.8, ["rotation", "scale", "opacity"], 1),
    tw(0.12, 0.71, ["opacity", "y"], 1),
    tw(3.44, 0.35, ["opacity", "y"], 0),
]


# ---- timing ----


def test_peak_after_last_draw_before_exit():
    assert fl.exit_at(LABEL, 3.86) == 3.44
    assert fl.peak_of(LABEL, 3.86) == pytest.approx(0.88 + fl.PEAK_SETTLE)


def test_peak_doodle_last_beat_and_idle_ignored():
    tweens = [
        tw(0.1, 0.4, ["opacity"], 1),
        tw(23.19, 0.35, ["opacity", "y"], 1),
        tw(23.29, 0.5, ["scaleX"]),
        tw(5.0, 30.0, ["rotation", "svgOrigin"], ease="none"),  # idle spin runs through the exit: ignored
        tw(24.404, 0.45, ["opacity"], 0),
    ]
    assert fl.peak_of(tweens, 24.954) == pytest.approx(23.79 + fl.PEAK_SETTLE)
    assert fl.late_draws(tweens, 24.954) == []
    assert fl.drawing_flag(tweens, 24.954) is None


def test_still_drawing_at_exit():
    tweens = [
        tw(0.1, 0.4, ["opacity"], 1),
        tw(9.8, 0.6, ["strokeDashoffset"]),
        tw(10.0, 0.45, ["opacity"], 0),
    ]
    assert fl.late_draws(tweens, 11.0) == [0.4]
    f = fl.drawing_flag(tweens, 11.0)
    assert f and f.code == "drawing"
    assert fl.peak_of(tweens, 11.0) == pytest.approx(10.0 - fl.EXIT_SLACK)  # what is on screen at the exit


def test_draw_within_slack_is_fine_and_window_end_is_exit():
    assert fl.late_draws([tw(9.0, 1.03, ["opacity"], 1), tw(10.0, 0.4, ["opacity"], 0)], 12) == []
    # no fade-out tween: the host window end is the exit; a draw running past it is still drawing
    assert fl.late_draws([tw(4.5, 1.0, ["clipPath"])], 5.0) == [0.5]


def test_peak_without_draws_is_middle():
    assert fl.peak_of([], 6.0) == 3.0


# ---- geometry ----


def test_overlap_with_face_margin():
    face = fl.xywh_to_box([900, 300, 200, 200])  # 900..1100 x 300..500
    near = fl.grow(face, fl.FACE_MARGIN)
    assert fl.overlap([1120, 400, 1300, 450], near)  # 20 px right of the face: inside the 40 px margin
    assert not fl.overlap([1150, 400, 1300, 450], near)  # 50 px away
    assert not fl.overlap([0, 0, 10, 10], [10, 0, 20, 10])  # touching edges share no area


def test_zoomed_box_scales_around_origin():
    assert fl.zoomed([100, 100, 200, 200], None) == [100, 100, 200, 200]
    assert fl.zoomed([100, 100, 200, 200], (2.0, 100.0, 100.0)) == [100, 100, 300, 300]


def test_text_flags_face_and_small():
    texts = [
        {"text": "big title", "box": [950, 450, 1300, 520], "px": 58, "color": "rgb(250,249,245)"},
        {"text": "tiny", "box": [100, 900, 200, 920], "px": 18, "color": "rgb(250,249,245)"},
    ]
    flags, rows = fl.text_flags(texts, [900, 300, 1100, 500], None)
    codes = {f.code for f in flags}
    assert codes == {"face", "small"}
    assert rows[1]["px"] == 18 and "contrast" not in rows[1]
    flags, _ = fl.text_flags(texts, None, None)  # no face box: face check skipped
    assert {f.code for f in flags} == {"small"}


# ---- colour ----


def test_parse_color():
    assert fl.parse_color("rgb(255, 214, 10)") == ((255, 214, 10), 1.0)
    assert fl.parse_color("rgba(250, 249, 245, 0.92)") == ((250, 249, 245), 0.92)
    assert fl.parse_color("#FFD60A") == ((255, 214, 10), 1.0)
    assert fl.parse_color("transparent") is None


def test_contrast_ratio_wcag():
    assert fl.contrast_ratio((255, 255, 255), (0, 0, 0)) == pytest.approx(21.0)
    assert fl.contrast_ratio((0, 0, 0), (0, 0, 0)) == pytest.approx(1.0)
    assert fl.contrast_ratio((118, 118, 118), (255, 255, 255)) == pytest.approx(4.54, abs=0.01)


def _frame(bg, ink, share=0.3):
    img = np.zeros((40, 100, 3), np.uint8)
    img[:] = bg
    img[:, : int(100 * share)] = ink
    return img


def test_background_and_contrast_flag():
    white = (250, 249, 245)
    assert fl.background_of(_frame((20, 20, 20), white), white) == (20, 20, 20)
    assert fl.background_of(_frame((20, 20, 20), white, 0.0), white) is None  # glyphs not on screen
    t = [{"text": "x", "box": [0, 0, 100, 40], "px": 40, "color": "rgb(250,249,245)"}]
    flags, rows = fl.text_flags(t, None, _frame((20, 20, 20), white))
    assert not flags and rows[0]["contrast"] > 10
    flags, rows = fl.text_flags(t, None, _frame((200, 200, 200), white))
    assert [f.code for f in flags] == ["contrast"] and rows[0]["contrast"] < fl.MIN_CONTRAST


def test_flags_merge_per_code():
    t = [{"text": f"t{i}", "box": [0, 0, 10, 10], "px": 10, "color": ""} for i in range(3)]
    flags, _ = fl.text_flags(t, None, None)
    assert len(flags) == 1 and "(+2 more)" in flags[0].message


# ---- reading the build ----

INDEX = """
      <div id="intro" class="clip" data-composition-id="intro" data-composition-src="compositions/intro.html" data-start="0.720" data-duration="3.860" data-track-index="1" data-track-kind="graphics" data-width="1920" data-height="1080"></div>
      <div id="big" class="clip" data-composition-id="big" data-composition-src="compositions/big.html" data-start="0.100" data-duration="5.020" data-track-index="2" data-track-kind="graphics" data-width="1920" data-height="1080" style="position:absolute;inset:0"></div>
      tl.set("#cam", { scale: 1.08, transformOrigin: "960px 400px" }, 0);
      tl.set("#cam", { scale: 1, transformOrigin: "960px 400px" }, 12.500);
"""


def test_hosts_and_zooms_of_index():
    hs = hosts_of(INDEX)
    assert [(h.id, h.start, h.dur, h.track) for h in hs] == [("big", 0.1, 5.02, 2), ("intro", 0.72, 3.86, 1)]
    zs = zooms_of(INDEX)
    assert zs == [(0.0, 1.08, 960.0, 400.0), (12.5, 1.0, 960.0, 400.0)]
    assert zoom_at(zs, 3.0) == (1.08, 960.0, 400.0)
    assert zoom_at(zs, 12.5) == (1.0, 960.0, 400.0)


def test_distinct_times_and_cells():
    assert distinct([1.0, 1.0004, 2.5]) == [1.0, 1.002, 2.5]
    assert where(0) == (1, 1) and where(11) == (1, 12) and where(12) == (2, 1)
