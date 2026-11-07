"""Style library: resolution order, find ranking, channel add/show, plug override, status line.

Every test points VEDIT_CONFIG_DIR at tmp_path; the real ~/.config/vedit is never touched.
"""

import json

import pytest

from vedit import channel as chan
from vedit.cli import main
from vedit.graphics import pack as packs
from vedit.graphics import pages, stylefind
from vedit.project import Project
from vedit.report import VeditError


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("VEDIT_CONFIG_DIR", str(tmp_path / "cfg"))
    return tmp_path / "cfg"


def mkpack(root, name, summary="", keywords=()):
    d = root / name
    d.mkdir(parents=True)
    (d / "pack.yaml").write_text(f"name: {name}\nsummary: {summary!r}\nkeywords: {list(keywords)}\n")
    return d


def project(tmp_path, extra=""):
    src = tmp_path / "a.mp4"
    src.write_bytes(b"x")
    (tmp_path / "project.yaml").write_text(f"slug: t\nlang: ar\n{extra}sources:\n  A: {{ file: {src} }}\n")
    return Project.load(tmp_path)


# ---- resolution order ----


def test_nearest_pack_wins_channel_global_builtin(cfg):
    assert packs.load("base", packs.pack_roots("c")).dirs[0] == packs.BUILTIN / "base"
    g = mkpack(cfg / "styles", "base", "global")
    assert packs.load("base", packs.pack_roots("c")).dirs[0] == g
    c = mkpack(cfg / "channels" / "c" / "styles", "base", "channel")
    assert packs.load("base", packs.pack_roots("c")).dirs[0] == c
    assert packs.load("base", packs.pack_roots("other")).dirs[0] == g  # another channel does not see it
    assert packs.load("base", packs.pack_roots()).dirs[0] == g


def test_drafts_is_not_a_pack_name(cfg):
    mkpack(cfg / "styles", "drafts")
    assert "drafts" not in [n for n, _, _ in packs.available()]
    with pytest.raises(VeditError):
        packs.load("drafts")


def test_unresolved_style_names_the_places_searched(cfg):
    with pytest.raises(VeditError) as e:
        packs.load("nope", packs.pack_roots("c"))
    m = e.value.message
    assert "channel:c" in m and "global" in m and "built-in" in m and str(cfg) in m


def test_style_order_cue_file_project_channel_global(cfg, tmp_path):
    (cfg).mkdir(parents=True)
    (cfg / "config.yaml").write_text("style: g\n")
    chan.save_channel("c", {"style": "ch"})
    p = project(tmp_path, "channel: c\n")
    assert chan.style_choice(p) == ("ch", "channel c")
    assert chan.style_choice(p, "file") == ("file", "cues.yaml")
    assert chan.style_choice(p, "file", "cue") == ("cue", "cue")
    p2 = project(tmp_path, "channel: c\nstyle: pr\n")
    assert chan.style_choice(p2) == ("pr", "project.yaml")
    p3 = project(tmp_path)
    assert chan.style_choice(p3) == ("g", "global config")
    (cfg / "config.yaml").write_text("")
    assert chan.style_choice(p3)[0] == "base"


# ---- find ----


def test_norm_stems_and_strips_diacritics():
    assert stylefind.norm("Doodles") == stylefind.norm("doodle") == stylefind.norm("DOODLING")
    assert stylefind.norm("Café") == "cafe" or stylefind.norm("Café") == stylefind.norm("cafe")
    assert stylefind.norm("عَرَبِي") == stylefind.norm("عربي")


def test_find_ranks_keywords_over_summary(cfg, capsys):
    assert main(["styles", "find", "warm doodle arabic"]) == 0
    out = capsys.readouterr().out
    assert out.index("yellow-doodle") < out.index("claude-violet")
    assert main(["--json", "styles", "find", "violet", "serif"]) == 0
    data = json.loads(capsys.readouterr().out)["data"]
    assert data["matches"][0]["name"] == "claude-violet" and data["matches"][0]["score"] == 6


def test_find_summary_words_count_less_and_no_match_is_empty(cfg, capsys):
    mkpack(cfg / "styles", "sum", summary="a calm look", keywords=["other"])
    mkpack(cfg / "styles", "kw", summary="x", keywords=["calm"])
    rows = [
        {"name": "sum", "summary": "a calm look", "keywords": ["other"]},
        {"name": "kw", "summary": "x", "keywords": ["calm"]},
    ]
    assert [r["name"] for r in stylefind.rank("calm", rows)] == ["kw", "sum"]
    assert main(["styles", "find", "zzzz"]) == 0
    assert "no style matches" in capsys.readouterr().out


def test_find_sees_channel_packs_only_with_that_channel(cfg, capsys):
    mkpack(cfg / "channels" / "c" / "styles", "neon", keywords=["neon"])
    main(["--json", "styles", "find", "neon"])
    assert json.loads(capsys.readouterr().out)["data"]["matches"] == []
    main(["--json", "styles", "find", "neon", "--channel", "c"])
    m = json.loads(capsys.readouterr().out)["data"]["matches"]
    assert m[0]["name"] == "neon" and m[0]["scope"] == "channel:c"


def test_show_prints_tokens_and_specimen(cfg, capsys):
    d = mkpack(cfg / "styles", "mine", "my look")
    assert main(["styles", "show", "mine"]) == 0
    assert "vedit style try mine" in capsys.readouterr().out
    (d / "specimen").mkdir()
    (d / "specimen" / "specimen.png").write_bytes(b"x")
    main(["styles", "show", "mine"])
    out = capsys.readouterr().out
    assert str(d / "specimen" / "specimen.png") in out and "colors:" in out and "own types:" in out
    assert main(["styles", "show", "nope"]) == 4  # bad_input


def test_list_shows_channel_scope(cfg, capsys):
    mkpack(cfg / "channels" / "c" / "styles", "neon", summary="glow")
    main(["styles", "--channel", "c"])
    assert "neon  (channel:c)  glow" in capsys.readouterr().out


# ---- channel add / show ----


def test_channel_add_then_show(cfg, capsys):
    assert (
        main(["channel", "add", "ali", "--style", "yellow-doodle", "--lang", "ar", "--accent", "#FFD60A"])
        == 0
    )
    assert chan.load_channel("ali") == {"style": "yellow-doodle", "lang": "ar", "accent": "#FFD60A"}
    assert main(["channel", "add", "ali", "--logos", "telegram, spark"]) == 0  # only the given flag changes
    assert chan.load_channel("ali")["style"] == "yellow-doodle"
    assert chan.load_channel("ali")["logos"] == ["telegram", "spark"]
    capsys.readouterr()
    assert main(["--json", "channel", "show", "ali"]) == 0
    d = json.loads(capsys.readouterr().out)["data"]
    assert d["channel"]["lang"] == "ar" and d["styles"] == [] and d["plug"] is None


def test_channel_add_rejects_unknown_style_bad_accent_bad_handle(cfg):
    assert main(["channel", "add", "ali", "--style", "nope"]) == 4  # bad_input
    assert main(["channel", "add", "ali", "--accent", "gold"]) == 2
    assert main(["channel", "add", "a/b"]) == 2
    assert not chan.channel_file("ali").exists()


def test_channel_style_may_be_a_channel_only_pack(cfg):
    mkpack(cfg / "channels" / "c" / "styles", "neon")
    assert main(["channel", "add", "c", "--style", "neon"]) == 0


def test_channel_show_unknown_and_default(cfg, capsys):
    assert main(["channel", "show", "ghost"]) == 4  # bad_input
    cfg.mkdir(parents=True, exist_ok=True)
    chan.save_channel("ali", {"lang": "ar"})
    (cfg / "config.yaml").write_text("channel: ali\n")
    assert main(["channel", "show"]) == 0
    assert "[default channel]" in capsys.readouterr().out


# ---- plug override ----


class _Env:
    def __init__(self, root, plug=None):
        self.paths = type("P", (), {"custom": root / "custom", "root": root})()
        self.plug, self.slug = plug, "demo"


def _preset(d, name):
    d.mkdir(parents=True)
    (d / "plug.yaml").write_text(f"name: {name}\nurl: {name}.com\n")


def test_plug_channel_preset_then_project_overrides(cfg, tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "project.yaml").write_text("channel: c\n")
    assert pages.plug_preset(_Env(root, "Brand"))[0] == {"name": "Brand"}
    _preset(cfg / "channels" / "c" / "plug", "chan")
    assert pages.plug_preset(_Env(root))[0]["url"] == "chan.com"
    _preset(root / "custom" / "plug", "proj")
    assert pages.plug_preset(_Env(root))[0]["url"] == "proj.com"


def test_plug_other_channel_preset_is_not_used(cfg, tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "project.yaml").write_text("channel: d\n")
    _preset(cfg / "channels" / "c" / "plug", "chan")
    assert pages.plug_preset(_Env(root))[0] == {"name": "demo"}


# ---- status line ----


def test_status_shows_style_and_origin(cfg, tmp_path, capsys):
    chan.save_channel("c", {"style": "yellow-doodle"})
    project(tmp_path, "channel: c\n")
    main(["status", "--project", str(tmp_path)])
    assert "style yellow-doodle (from channel c)" in capsys.readouterr().out
    (tmp_path / "cues.yaml").write_text("style: claude-violet\ncues: []\n")
    main(["--json", "status", "--project", str(tmp_path)])
    s = json.loads(capsys.readouterr().out)["data"]["style"]
    assert s == {"name": "claude-violet", "from": "cues.yaml", "found": True}


def test_status_unresolved_style_is_an_error_naming_places(cfg, tmp_path, capsys):
    project(tmp_path, "style: nope\n")
    assert main(["status", "--project", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "style nope (from project.yaml) does not resolve" in out and "searched" in out
