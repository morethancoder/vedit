"""Doodle library: deterministic drawing, spec validation, every library scene, pack templates and doodle.yaml."""

import hashlib
import json
import re
from types import SimpleNamespace

import pytest

from vedit.cli import main
from vedit.doodles import library, spec, style
from vedit.doodles.scene import Style
from vedit.graphics import pack as packs
from vedit.graphics import pages
from vedit.graphics.cues import Cue
from vedit.graphics.plan import Placement

BEATS = {"bot": 0.5, "flood": 2.2, "second": 3.9, "crash": 5.6}
SHORT = {
    "lang": "ar",
    "elements": [
        {"beat": "bot", "id": "bot", "bot": {}, "label": "البوت"},
        {"beat": "mail", "id": "mail", "envelope": {"w": 120}, "label": "رسائل"},
        {"beat": "mail", "arrow": {"from": "mail", "to": "bot"}, "label": "آلاف"},
        {"beat": "crash", "text": "طاح!", "at": [960, 900], "color": "warn"},
    ],
}


def svg_of(name, seed=None, beats=BEATS, st=None, dur=14.0):
    sp, s0 = library.resolve(name)
    return spec.draw(sp, s0 if seed is None else seed, dur, beats, st).svg()


def test_same_spec_same_svg_bytes():
    a, b = svg_of("flood"), svg_of("flood")
    assert a == b and a.startswith('<svg class="dz"')
    assert svg_of("flood", seed=7) != a  # the wobble is the seed's
    assert svg_of(SHORT) == svg_of(json.loads(json.dumps(SHORT)))


def test_flood_matches_t_golden():
    # T tools/doodles.py + doodles_tele.py `flood` with these beats, 14 s, T's colours: byte-identical paths
    # (checked against T's own render when the library was ported; this pins it)
    yel = Style(ink="#FAF9F5", accent="#FFD60A", soft="#FFE45C", warn="#FF7A59")
    h = hashlib.sha256(svg_of("flood", st=yel).encode()).hexdigest()[:16]
    assert h == GOLDEN_FLOOD


@pytest.mark.parametrize("name", library.names())
def test_every_library_scene_is_valid_and_draws(name):
    sp = library.scene(name)
    assert spec.check(sp, name) == []
    assert sp.get("lang") in ("ar", "en") and sp.get("about")
    order = spec.beat_names(sp)
    s = spec.draw(sp, 1, 12.0, {}, None)  # no beats heard: spaced evenly
    assert s.svg().count("<path") > 5 and s.draws and s.labs
    assert all(t + d <= 12.0 - 0.75 + 1e-6 for _, _, t, d in s.draws)  # all drawn before the fade
    ar = any(re.search(r"[؀-ۿ]", st.get("text", "")) for steps in sp["beats"].values() for st in steps)
    assert ar == (sp["lang"] == "ar") and len(order) >= 3


def test_library_has_t_and_c_scenes():
    t = {"path", "request", "dms", "flood", "funnel", "chart", "gate", "broadcast", "experience", "nativeapp"}
    t |= {"mcp", "login"}
    c = {"remote", "pairing", "alwayson", "botapi", "chatid", "bot", "harness"}
    assert t | c == set(library.names())


def test_arabic_labels_write_right_to_left_latin_left_to_right():
    s = spec.draw(library.scene("funnel"), 1, 14.0, {}, None)
    html = "".join(s.labels_html)
    assert 'class="dz-t ar k' in html and 'dir="rtl"' in html
    modes = {m for *_, m in s.labs}
    assert modes == {"r", "w"}


@pytest.mark.parametrize(
    "bad, msg",
    [
        ({"beats": {"a": [{"pen": 1, "shapes": [{"bott": {"at": [1, 2]}}]}]}}, "did you mean 'bot'"),
        ({"beats": {"a": [{"pen": 1, "shapes": [{"bot": {"at": [1, 2], "w": 3}}]}]}}, "bot needs 'h'"),
        (
            {"beats": {"a": [{"pen": 1, "shapes": [{"laptop": {"at": [1, 2], "w": 3, "colour": "x"}}]}]}},
            "has no 'colour'",
        ),
        ({"beats": {"a": [{"shapes": []}]}}, "needs `pen: <seconds>`"),
        ({"beats": {"a": [{"text": "x"}]}}, "text needs `at: [x, y]`"),
        ({"beats": {"a": [{"pen": 1, "into": "nope", "shapes": []}]}}, "names no earlier pass"),
        ({"beat": {}}, "unknown key 'beat'; did you mean 'beats'"),
        ({"elements": [{"beat": "a", "arrow": {"from": "x", "to": [1, 2]}}]}, "id of an earlier element"),
        ({"elements": [{"beat": "a", "bot": {}, "phone": {}}]}, "one shape per element"),
        ({"elements": [{"bot": {}}]}, "needs `beat: <name>`"),
        ("flood", None),
    ],
)
def test_spec_validation_messages(bad, msg):
    errs = spec.check(bad) if isinstance(bad, dict) else spec.check(library.scene(bad))
    if msg is None:
        assert errs == []
    else:
        assert any(msg in e for e in errs), errs


def test_cue_check_names_unknown_scene_and_beats():
    assert "did you mean 'flood'" in library.check_cue({"scene": "flod", "beats": {}}, "c")[0]
    errs = library.check_cue({"scene": "flood", "beats": {"bot": "x", "boom": "y"}}, "c")
    assert errs == ["c: beat 'boom' is not in the scene (beats: bot, flood, second, crash)"]
    assert library.check_cue({"scene": SHORT, "beats": {"mail": "x"}}, "c") == []


def test_short_form_expands_right_to_left_for_arabic():
    full = spec.expand(SHORT, "ar")
    assert list(full["beats"]) == ["bot", "mail", "crash"]
    bot_x = full["beats"]["bot"][0]["shapes"][0]["bot"]["at"][0]
    mail_x = full["beats"]["mail"][0]["shapes"][0]["envelope"]["at"][0]
    assert bot_x > mail_x  # first element on the right
    en = spec.expand({**SHORT, "lang": "en"})
    assert en["beats"]["bot"][0]["shapes"][0]["bot"]["at"][0] < 960
    arrow = full["beats"]["mail"][2]["shapes"][0]["arrow"]
    assert mail_x < arrow["a"][0] < arrow["b"][0] < bot_x  # edge to edge, not centre to centre
    assert spec.check(full) == []


def test_resolve_beats_spaces_missing_and_starts_early():
    out = spec.resolve_beats(["a", "b", "c"], 10.0, {"b": 4.0})
    assert out == {"a": 0.12, "b": 4.0, "c": 7.0}
    assert spec.resolve_beats(["a"], 10.0, {"a": 3.0}) == {"a": 0.12}


@pytest.mark.parametrize("name", ["base", "yellow-doodle", "claude-violet"])
def test_doodle_template_renders_in_every_pack(name, tmp_path):
    pk = packs.load(name, [packs.BUILTIN])
    assert packs.check(pk) == []
    cue = Cue("dd-x", "doodle", name, {"scene": "flood", "beats": {"bot": "x"}}, "A", 10.0, 10.0, 22.0)
    cue.beats = {"bot": 11.0, "crash": 15.0}
    env = pages.Env(SimpleNamespace(root=tmp_path, custom=tmp_path / "custom"), "ar")
    pg = pages.render(Placement(cue, 10.0, 12.0, 6), pk, env)
    assert "{{" not in pg.html and '<svg class="dz"' in pg.html and "const DRAW = [[" in pg.html
    st, look = style.load(pk)
    assert f'fill="{st.accent}"' in pg.html and look["latin"] in pg.html
    assert pg.sounds[:2] == [("focus", 0.0), ("beat", 1.0)]
    fam = look["arabic"].split(",")[0].strip().strip('"')
    assert f'font-family: "{fam}"' in pg.html  # the @font-face for the lettering is in the page


def test_pack_colours_and_channel_accent():
    yel = packs.load("yellow-doodle", [packs.BUILTIN])
    assert style.load(yel)[0].accent == "#FFD60A"
    assert style.load(yel, "#00FF88")[0].accent == "#00FF88"  # `accent: accent` follows a channel accent
    vio = packs.load("claude-violet", [packs.BUILTIN])
    st, look = style.load(vio)
    assert (st.accent, st.soft) == ("#B9A5FF", "#CDBEFF") and "Caveat" in look["latin"]
    assert style.load(packs.load("base", [packs.BUILTIN]))[0].wobble == 0.8


def test_doodle_yaml_problems_are_reported(tmp_path):
    d = tmp_path / "scratch"
    (d / "types").mkdir(parents=True)
    (d / "pack.yaml").write_text("name: scratch\nextends: yellow-doodle\n")
    (d / "doodle.yaml").write_text("strok: '#fff'\nwidth: -1\nlettering: {latin: '\"Nope\", cursive'}\n")
    pk = packs.load("scratch", [tmp_path, packs.BUILTIN])
    errs = "\n".join(packs.check(pk))
    assert "unknown key 'strok'" in errs and "width must be a number > 0" in errs
    assert "lettering.latin font 'Nope' is not in pack.yaml fonts" in errs


def test_doodle_list_command(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("VEDIT_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.chdir(tmp_path)
    assert main(["doodle", "list", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)["data"]["scenes"]
    assert {r["name"] for r in data} == set(library.names())
    assert next(r for r in data if r["name"] == "gate")["beats"][4] == "no"


def test_preview_project_is_written_without_rendering(tmp_path):
    from vedit.commands import doodle

    pk = packs.load("claude-violet", [packs.BUILTIN])
    hf, dur = doodle.build_preview("remote", "remote", pk, tmp_path, "en")
    assert dur == pytest.approx(0.12 + 1.7 * 2 + 3.0)
    html = (hf / "compositions" / "dz-preview.html").read_text()
    assert "your session" in html and "#B9A5FF" in html
    assert (hf / "assets" / "gsap.min.js").is_file() and (
        hf / "assets" / "fonts" / "caveat-700.woff2"
    ).is_file()
    assert 'data-composition-src="compositions/dz-preview.html"' in (hf / "index.html").read_text()


GOLDEN_FLOOD = "aa8bbcf10549a984"


def test_pages_keep_labels_readable_in_a_small_panel():
    from vedit.doodles import library
    from vedit.doodles import spec as dspec

    sp, _ = library.resolve("funnel")
    pgs = dspec.pages(sp, 578, 504)
    assert len(pgs) > 1
    assert [n for pg in pgs for n in pg["beats"]] == list(sp["beats"])  # every beat once, in order
    for pg in pgs:
        b = dspec.content_box(pg, pad=24)
        k = min(578 / (b[2] - b[0]), 504 / (b[3] - b[1]))
        assert dspec._min_label(pg["beats"]) * k >= 38 - 0.5
    assert dspec.pages(sp, 4000, 3000) == [sp]  # room enough: one page, the scene untouched
