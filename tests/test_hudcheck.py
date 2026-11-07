from vedit.formats import hudcheck


def test_box_in_the_action_column_is_flagged():
    flags = hudcheck.check(
        {"g": {"x": 700, "y": 1300, "w": 300, "h": 200}}, ["instagram-reels"], (1080, 1920), set()
    )
    assert {f["region"] for f in flags} >= {"right action column"}


def test_box_inside_the_clear_area_passes():
    assert hudcheck.check({"g": {"x": 200, "y": 600, "w": 500, "h": 300}}, ["instagram-reels", "tiktok"],
                          (1080, 1920), set()) == []  # fmt: skip


def test_cards_may_reach_the_side_margins_but_text_may_not():
    box = {"g": {"x": 0, "y": 300, "w": 1080, "h": 600}}
    assert hudcheck.check(box, ["instagram-feed"], (1080, 1350), {"g"}) == []
    assert {f["region"] for f in hudcheck.check(box, ["instagram-feed"], (1080, 1350), set())} == {
        "left edge", "right edge"}  # fmt: skip


def test_mock_draws_on_an_output_frame():
    import numpy as np

    img = np.zeros((1920, 1080, 3), np.uint8)
    out = hudcheck.mock(img, ["tiktok"])
    assert out.shape == img.shape and out.any()
