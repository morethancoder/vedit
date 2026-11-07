import json

import pytest

from vedit import cli
from vedit import formats as fm
from vedit.report import VeditError


def test_every_platform_has_geometry_and_sources():
    for pid, p in fm.platforms().items():
        assert p["aspect"] in fm.ASPECTS, pid
        assert all(p["safe"][e] is not None and p["safe"][e] >= 0 for e in fm.EDGES), pid
        assert p["confidence"] in ("high", "medium", "low"), pid
        assert p["sources"] or p.get("fallback"), pid
        box = fm.safe_box([pid], tuple(p["canvas"]))
        assert box.w > 0 and box.h > 0, pid


def test_union_takes_the_strictest_edge():
    box = fm.safe_box(["instagram-reels", "tiktok", "youtube-shorts", "facebook-reels"], (1080, 1920))
    assert (box.x, box.y, box.x1, box.y1) == (120, 288, 853, 1248)


def test_insets_scale_to_the_canvas():
    i = fm.insets("instagram-reels", (2160, 3840))
    assert i["top"] == 538 and i["bottom"] == 1344


def test_fallback_platforms_use_the_strictest_9x16():
    tg = fm.platform("telegram-stories")
    assert tg.get("fallback") and tg["safe"] == {"top": 288, "bottom": 672, "left": 120, "right": 227}


def test_hud_regions_scaled_and_bars_when_missing():
    names = [r["name"] for r in fm.hud("instagram-reels", (1080, 1920))]
    assert "right action column" in names
    bars = fm.hud("instagram-feed", (1080, 1350))
    assert {r["name"] for r in bars} >= {"top bar", "bottom bar"}


def test_visible_fraction_of_a_crop():
    assert round(fm.visible("16:9", "9:16")["width"], 3) == 0.316
    assert fm.visible("9:16", "3:4")["height"] == 0.75


def test_wrong_aspect_and_unknown_platform_are_bad_input():
    with pytest.raises(VeditError) as e:
        fm.safe_box(["instagram-reels"], (1920, 1080))
    assert e.value.code == "bad_input"
    with pytest.raises(VeditError):
        fm.platform("myspace")
    with pytest.raises(VeditError):
        fm.canvas("5:7")


def test_formats_command_json(capsys):
    assert cli.main(["formats", "instagram-reels", "tiktok", "--json"]) == 0
    d = json.loads(capsys.readouterr().out)["data"]
    assert d["union"]["safe_box"] == {"x": 120, "y": 269, "w": 733, "h": 979}
    assert cli.main(["formats", "nope", "--json"]) == 4
