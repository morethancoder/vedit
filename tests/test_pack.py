from pathlib import Path

import pytest

from vedit.graphics import pack
from vedit.report import VeditError


def mkpack(root: Path, name: str, extends=None, types=None, logos=()):
    d = root / name
    (d / "types").mkdir(parents=True)
    (d / "logos").mkdir()
    (d / "pack.yaml").write_text(
        f"name: {name}\n" + (f"extends: {extends}\n" if extends else "") + "colors: {a: 1}\n"
    )
    for t, text in (types or {}).items():
        (d / "types" / f"{t}.html").write_text(text)
    for lg in logos:
        (d / "logos" / f"{lg}.svg").write_text("<svg/>")


TPL = """<!-- vedit
slots:
  title: {required: true, help: "the title"}
  logo: {kind: logo}
  flag: {kind: bool}
  n: {kind: number}
  tags: {kind: list}
  beats: {kind: beats}
-->
<style>.a{color:red}</style>
<div>{{title}}</div>
<script>var x = 1;</script>
"""


@pytest.fixture
def roots(tmp_path):
    mkpack(
        tmp_path, "base", types={"label": TPL, "chip": "<!-- vedit\nslots: {}\n-->\n<b/>"}, logos=["octopus"]
    )
    mkpack(
        tmp_path, "mine", extends="base", types={"label": TPL.replace("title:", "headline:")}, logos=["own"]
    )
    return [tmp_path]


def test_template_parsing(roots):
    t = pack.load("base", roots).template("label")
    assert list(t.slots) == ["title", "logo", "flag", "n", "tags", "beats"]
    assert t.slots["title"].required and t.slots["title"].help == "the title"
    assert t.slots["logo"].kind == "logo" and not t.slots["logo"].required
    assert t.style == ".a{color:red}" and t.script == "var x = 1;" and t.body == "<div>{{title}}</div>"
    assert t.pack == "base"


def test_bad_slot_kind(tmp_path):
    mkpack(tmp_path, "base", types={"x": "<!-- vedit\nslots:\n  a: {kind: nope}\n-->"})
    with pytest.raises(VeditError, match="unknown kind"):
        pack.load("base", [tmp_path]).template("x")


def test_extends_falls_back_to_base(roots):
    p = pack.load("mine", roots)
    assert p.template("label").pack == "mine" and "headline" in p.template("label").slots
    assert p.template("chip").pack == "base"
    assert p.types() == ["chip", "label"]
    assert sorted(p.logos()) == ["octopus", "own"]
    with pytest.raises(VeditError, match="no template for cue type 'zzz'"):
        p.template("zzz")


def test_load_errors(roots, tmp_path):
    with pytest.raises(VeditError, match="did you mean 'mine'"):
        pack.load("mina", roots)
    mkpack(tmp_path, "a", extends="b")
    mkpack(tmp_path, "b", extends="a")
    with pytest.raises(VeditError, match="loops"):
        pack.load("a", roots)


def test_pack_data_merges(roots):
    assert (
        pack.load("mine", roots).data["colors"] == {"a": 1}
        and pack.load("mine", roots).data["name"] == "mine"
    )


def test_check_fields(roots):
    t = pack.load("base", roots).template("label")
    logos = pack.load("base", roots).logos()
    assert (
        pack.check_fields(
            t, {"title": "x", "logo": "octopus", "flag": True, "n": 2, "tags": ["a"]}, "c", logos
        )
        == []
    )
    assert (
        pack.check_fields(t, {"title": "x", "at": "w", "near": "A 1", "until": "end"}, "c") == []
    )  # cue keys
    errs = pack.check_fields(t, {"titel": "x"}, "c")
    assert any("unknown field 'titel'" in e and "did you mean 'title'" in e for e in errs)
    assert any("needs 'title'" in e for e in errs)
    assert any("should be bool" in e for e in pack.check_fields(t, {"title": "x", "flag": "yes"}, "c"))
    assert any("should be number" in e for e in pack.check_fields(t, {"title": "x", "n": True}, "c"))
    assert any("should be list" in e for e in pack.check_fields(t, {"title": "x", "tags": "a"}, "c"))
    assert any("should be beats" in e for e in pack.check_fields(t, {"title": "x", "beats": {"a": 1}}, "c"))
    assert any("logo 'zz'" in e for e in pack.check_fields(t, {"title": "x", "logo": "zz"}, "c", logos))


def test_builtin_templates_all_parse():
    p = pack.load("base")
    assert {"label", "chip", "kinetic", "big-number", "doodle", "screen", "chapter", "plug", "custom"} <= set(
        p.types()
    )
    for t in p.types():
        p.template(t)


@pytest.mark.parametrize(
    "tpl,ctx,out",
    [
        ("<b>{{x}}</b>", {"x": "a<b>&\"'"}, "<b>a&lt;b&gt;&amp;&quot;&#x27;</b>"),
        ("{{&x}}", {"x": "<i>"}, "<i>"),
        ("{{a.b.c}}", {"a": {"b": {"c": 5}}}, "5"),
        ("{{a.b}}", {"a": {}}, ""),
        ("{{missing}}", {}, ""),
        ("{{x}}", {"x": 1.5}, "1.5"),
        ("{{x}}", {"x": 2.0}, "2"),
        ("{{x}}", {"x": None}, ""),
        ("{{#xs}}[{{.}}]{{/xs}}", {"xs": ["a", "b"]}, "[a][b]"),
        ("{{#xs}}{{n}},{{/xs}}", {"xs": [{"n": 1}, {"n": 2}]}, "1,2,"),
        ("{{#d}}{{k}}{{/d}}", {"d": {"k": "v"}}, "v"),
        ("{{#t}}yes{{/t}}{{^t}}no{{/t}}", {"t": True}, "yes"),
        ("{{#t}}yes{{/t}}{{^t}}no{{/t}}", {"t": ""}, "no"),
        ("{{^xs}}none{{/xs}}", {"xs": []}, "none"),
        ("{{#xs}}{{#xs}}-{{/xs}}{{/xs}}", {"xs": [{"xs": [1, 2]}]}, "--"),
        ("{{#a}}{{x}}{{/a}}", {"a": {"y": 1}, "x": "outer"}, "outer"),
    ],
)
def test_render(tpl, ctx, out):
    assert pack.render(tpl, ctx) == out


def test_render_errors():
    with pytest.raises(VeditError, match="not closed"):
        pack.render("{{#a}}x", {"a": True})
    with pytest.raises(VeditError, match="unexpected close"):
        pack.render("x{{/a}}", {})


# ---- pack checker ----


def test_builtin_packs_have_no_problems():
    for name in ("base", "yellow-doodle"):
        assert pack.check(pack.load(name, [pack.BUILTIN])) == []


def test_syntax_scan_checks_skipped_sections():
    assert pack.syntax("{{#a}}{{^b}}x{{/b}}{{/a}}") == []
    assert pack.syntax("{{#a}}x") == ["section 'a' is not closed"]
    assert pack.syntax("x{{/a}}") == ["unexpected close {{/a}}"]
    assert pack.syntax("{{#a}}{{#b}}{{/a}}{{/b}}")[0] == "{{/a}} closes {{#b}}"


def broken(root: Path) -> None:
    d = root / "broken"
    for sub in ("types", "partials", "logos"):
        (d / sub).mkdir(parents=True)
    (d / "pack.yaml").write_text(
        "name: broken\nextends: base\ncolours: {accent: red}\n"
        "fonts: [{family: X, file: fonts/nope.ttf}]\n"
        "sfx: {label: [nosound, 0.3], chip: [click, -1]}\n"
        "advances: nope.json\nlogo_motion: {spin: [ghost]}\n"
        "motion: {ease_in: 3, out: fast}\n"
    )
    (d / "types" / "label.html").write_text("<!-- vedit\nslots:\n  a: {kind: nope}\n-->\n<b/>")
    (d / "types" / "chip.html").write_text("<!-- vedit\nslots: [\n-->\n<b/>")
    (d / "types" / "kinetic.html").write_text("<!-- vedit\nslots: {}\n-->\n<b>{{#w}}x</b>")
    (d / "partials" / "extra.html").write_text("<script>{{/z}}</script>")


def test_check_reports_every_problem_at_once(tmp_path):
    broken(tmp_path)
    errs = pack.check(pack.load("broken", [tmp_path, pack.BUILTIN]))
    text = "\n".join(errs)
    for want in (
        "unknown key 'colours'; did you mean 'colors'?",
        "font file 'fonts/nope.ttf' is not in the pack",
        "sfx.label sound sfx/nosound.mp3 is not in the pack",
        "sfx_files has no length for 'nosound'",
        "sfx.chip must be [sound, gain]",
        "advances file 'nope.json' is not in the pack",
        "logo_motion.spin names 'ghost'",
        "motion.ease_in must be a GSAP ease",
        "motion.out must be a number",
        "unknown kind 'nope'",
        "slot header is not valid YAML",
        "kinetic.html: section 'w' is not closed",
        "extra.html: unexpected close {{/z}}",
    ):
        assert want in text, (want, errs)


def test_check_flags_a_missing_motion_token_and_name_mismatch(tmp_path):
    d = tmp_path / "base"
    d.mkdir()
    (d / "pack.yaml").write_text(
        "name: other\nmotion: {ease_in: power3.out}\nthemes: {dark: {text: '#fff'}}\n"
    )
    errs = pack.check(pack.load("base", [tmp_path]))
    assert any("themes.dark lacks sub, kicker, shadow" in e for e in errs)
    assert any("themes.light is missing" in e for e in errs)
    assert any("motion lacks out" in e for e in errs)
    assert any("name 'other' differs from its folder 'base'" in e for e in errs)


# ---- user packs ----


def test_user_packs_load_from_config_dir_at_call_time(tmp_path, monkeypatch):
    monkeypatch.setenv("VEDIT_CONFIG_DIR", str(tmp_path / "cfg"))
    assert pack.pack_roots() == [tmp_path / "cfg" / "styles", pack.BUILTIN]
    d = tmp_path / "cfg" / "styles" / "scratch"
    (d / "types").mkdir(parents=True)
    (d / "pack.yaml").write_text(
        "name: scratch\nextends: yellow-doodle\nsummary: test\ncolors: {accent: '#7C5CFF'}\n"
        "motion: {ease_in: expo.out}\n"
    )
    (d / "types" / "label.html").write_text(TPL)
    p = pack.load("scratch")
    assert [x.name for x in p.dirs] == ["scratch", "yellow-doodle", "base"]
    src = p.type_sources()
    assert src["label"] == "scratch" and src["chip"] == "yellow-doodle" and src["custom"] == "base"
    assert p.template("chip").pack == "yellow-doodle"
    assert p.template("label").slots["title"].required
    assert p.data["colors"]["accent"] == "#7C5CFF" and p.data["colors"]["ivory"] == "#FAF9F5"
    assert p.data["motion"]["ease_in"] == "expo.out" and p.data["motion"]["out"] == 0.35
    assert p.file("fonts/IBMPlexSansArabic-Bold.ttf") is not None  # files fall back too
    assert pack.check(p) == []
    names = [(n, r) for n, _, r in pack.available()]
    assert ("scratch", tmp_path / "cfg" / "styles") in names and ("base", pack.BUILTIN) in names


def test_motion_tokens_reach_templates():
    p = pack.load("base", [pack.BUILTIN])
    assert set(p.data["motion"]) >= {"ease_in", "ease_out", "out", "out_lead", "stagger"}
    label = p.template("label").script
    assert "{{m.ease_in}}" in label and "D - {{m.out_lead}}" in label and '"power3.out"' not in label


def test_big_number_color_accent_follows_pack():
    from types import SimpleNamespace

    from vedit.graphics import pages

    p = SimpleNamespace(big={"fs": 200, "top": 300, "width": 600})
    pk = SimpleNamespace(data={})
    c = {"accent": "#7452E8", "ivory": "#FAF9F5"}
    for given, want in (("accent", "#7452E8"), ("#123456", "#123456"), (None, "#FAF9F5")):
        ctx = {"color": given, "c": c}
        pages._big(p, ctx, pk)
        assert ctx["color"] == want
