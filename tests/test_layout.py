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
    assert (
        c["x"] + c["w"] <= 780 + 0.5 and abs(c["x"] - (1080 - c["x"] - c["w"])) < 0.6
    )  # centred on the frame


def test_clear_span_narrows_for_action_columns_and_stays_centred():
    g = geo()
    assert g.clear(300, 500) == (227, 853)  # the right inset (227) mirrored on the left: centred on the frame
    x0, x1 = g.clear(900, 1100)
    assert x1 <= 780 and x0 + x1 == 1080


def test_big_word_spans_the_crop_and_tucks_behind_the_head():
    g = geo()
    b = lay.big(g, Track(bottom=500), 0, 5, "1.7M", {})
    assert g.points[0]["x"] <= b["left"] and b["left"] + b["width"] <= g.points[0]["x"] + g.crop_w
    assert b["top"] < 200 and b["side"] == "center"


def test_wrap_css_targets_the_band():
    g = geo()
    css = lay.wrap_css(g, "label", lay.Slot(700, 1100, False))
    assert "left: 120px" in css and "bottom: 820px" in css and "width: 733px" in css


def test_label_text_centres_in_the_band():
    css = lay.wrap_css(geo(), "label", lay.Slot(700, 1100, False))
    assert ".txt { align-items: center !important; text-align: center !important; }" in css


def test_split_area_is_centred_and_stays_above_the_side_buttons():
    g = geo(platforms=("instagram-reels", "tiktok"))
    x0, y0, x1, y1 = lay.split_area(g)
    assert abs(x0 - (1080 - x1)) < 0.6 and y0 >= g.safe.y and y1 <= 1920 * lay.SPLIT
    assert (
        y1 + lay.PANEL_MARGIN <= 840 + 0.5
    )  # tiktok's action column starts at y 840: the panel stops above it


def test_fit_centres_the_drawing_in_the_area():
    c = lay.fit((100, 300, 900, 800), (0, 0, 1600, 500))
    assert c["k"] == 0.5 and c["w"] == 800 and c["x"] == 100 and c["y"] == 300 + (500 - 250) / 2


def test_split_camera_puts_the_whole_head_under_the_seam_captions():
    g = geo()
    area = lay.split_area(g)
    c = lay.split_camera(g, Track(bottom=500), 0, 5, area)
    seam = area[3] + lay.PANEL_MARGIN
    assert c["cap_dy"] == round(seam - g.caption_top, 1)  # captions move up to the seam
    fh = 300 * g.s
    face_mid = c["oy"] + c["dy"]  # the zoom pivots on the face centre, then slides by dy
    head_top = face_mid - lay.HEAD_ROOM * fh * c["z"]
    assert head_top >= seam + g.caption_h + 16 - 0.5 and c["z"] < 1
    assert c["oy"] + (1920 - c["oy"]) * c["z"] + c["dy"] >= 1920  # the zoomed camera still reaches the bottom
    assert c["fill_h"] >= seam
