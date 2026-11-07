from vedit.formats import layout as lay
from vedit.project import Output


class Track:
    def __init__(self, bottom):
        self.bottom = bottom

    def over(self, s, e):
        return [[800, self.bottom - 300, 300, 300]], True

    def samples(self, s, e):
        return [(s, [800, self.bottom - 300, 300, 300])]


def geo(captions="burned", platforms=("instagram-reels", "tiktok")):
    o = Output("r", "short", "9:16", list(platforms), None, captions)
    return lay.geometry(o, points=[{"t": 0, "x": 656}, {"t": 10, "x": 656}], t0=0, t1=10)


def test_geometry_scale_and_safe_box():
    g = geo()
    assert round(g.s, 4) == 1.7778 and g.safe.x == 120 and g.safe.y1 == 1920 - 672


def test_band_sits_under_the_face_above_captions():
    g = geo()
    s = lay.band(g, Track(bottom=400), "label", 0, 5)  # face bottom 400 src px = 711 out px
    assert s.top == round(711.1 + lay.FACE_GAP, 1) and s.bottom == round(g.caption_top - lay.CAPTION_GAP, 1)
    assert not s.pause_captions


def test_band_pauses_captions_when_too_short():
    g = geo()
    s = lay.band(g, Track(bottom=560), "label", 0, 5)  # face reaches 995 px: no room above the captions
    assert s.pause_captions and s.bottom == g.safe.y1


def test_kinetic_size_fits_band_width():
    s = lay.band(geo(), Track(bottom=400), "kinetic", 0, 5, em=20.0)
    assert s.fs == max(44.0, round(0.95 * 733 / 20, 1))


def test_card_is_full_width_unless_side_ui_reaches_its_rows():
    g = geo(platforms=("instagram-stories",))
    c = lay.card(g)
    assert c["w"] == 1080 and c["h"] == 607.5 and abs(c["y"] + c["h"] / 2 - (g.safe.y + g.safe.h / 2)) < 0.1
    g = geo()  # tiktok's action column (x >= 780 below y 840) reaches into the card's rows
    c = lay.card(g)
    assert c["x"] == 0 and c["x"] + c["w"] <= 780 + 0.5


def test_clear_span_narrows_for_action_columns():
    g = geo()
    assert g.clear(300, 500) == (120, 853) and g.clear(900, 1100)[1] <= 780


def test_big_word_spans_the_crop_and_tucks_behind_the_head():
    g = geo()
    b = lay.big(g, Track(bottom=500), 0, 5, "1.7M", {})
    assert g.points[0]["x"] <= b["left"] and b["left"] + b["width"] <= g.points[0]["x"] + g.crop_w
    assert b["top"] < 200 and b["side"] == "center"


def test_wrap_css_targets_the_band():
    g = geo()
    css = lay.wrap_css(g, "label", lay.Slot(700, 1100, False))
    assert "left: 120px" in css and "bottom: 820px" in css and "width: 733px" in css
