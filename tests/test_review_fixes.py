"""Phase-05 review fixes: spec injection, accent chain, plug/engine keys, name and path confinement."""

import json
from types import SimpleNamespace

import pytest

from vedit.commands import build as build_cmd
from vedit.commands.styles import channel_of
from vedit.doodles import spec
from vedit.doodles.scene import Style
from vedit.graphics import pack as packs
from vedit.graphics import pages
from vedit.graphics.cues import Cue, _inside
from vedit.graphics.plan import Placement
from vedit.project import Project, ProjectError
from vedit.report import VeditError
from vedit.styleauthor import drafts

EVIL = 'red"><script>alert(1)</script>'


def full(**text):
    return {"beats": {"b": [{"text": "hi", "at": [100, 100], **text}]}}


@pytest.mark.parametrize(
    "extra",
    [
        {"color": EVIL},
        {"color": "red;x"},
        {"size": "big"},
        {"weight": "bold"},
        {"d": "x"},
        {"mode": "zzz"},
    ],
)
def test_text_step_values_are_validated(extra):
    assert spec.check(full(**extra))


@pytest.mark.parametrize(
    "extra",
    [
        {"color": "accent"},
        {"color": "#FFD60A"},
        {"color": "ink2"},
        {"size": 60, "weight": 700, "mode": "f", "d": 0.5},
    ],
)
def test_good_text_values_pass(extra):
    assert spec.check(full(**extra)) == []


def test_shape_color_and_short_form_are_validated():
    sh = {"beats": {"b": [{"pen": 1, "shapes": [{"circle": {"at": [5, 5], "r": 9, "color": EVIL}}]}]}}
    assert spec.check(sh)
    assert spec.check({"elements": [{"beat": "b", "text": "x", "at": [1, 1], "color": EVIL}]})
    assert spec.check({"elements": [{"beat": "b", "text": "x", "at": [1, 1], "size": "big"}]})


def test_style_color_escapes():
    out = Style().color(EVIL)
    assert "<" not in out and '"' not in out


def test_arrow_endpoint_naming_an_arrow_is_rejected():
    s = {
        "elements": [
            {"beat": "b", "id": "a", "bot": {}},
            {"beat": "b", "id": "c", "envelope": {}},
            {"beat": "b", "id": "ar", "arrow": {"from": "a", "to": "c"}},
            {"beat": "b", "arrow": {"from": "ar", "to": "c"}},
        ]
    }
    errs = spec.check(s)
    assert errs and "is an arrow" in errs[0]


def test_build_env_uses_channel_accent(tmp_path, monkeypatch):
    monkeypatch.setenv("VEDIT_CONFIG_DIR", str(tmp_path / "cfg"))
    (tmp_path / "cfg" / "channels" / "ch").mkdir(parents=True)
    (tmp_path / "cfg" / "channels" / "ch" / "channel.yaml").write_text("accent: '#123456'\n")
    p = SimpleNamespace(accent=None, channel="ch", root=tmp_path)
    assert build_cmd.chan.effective_accent(p)[0] == "#123456"
    import inspect

    assert "chan.effective_accent(project)[0]" in inspect.getsource(build_cmd)


def plug_env(tmp_path):
    paths = SimpleNamespace(root=tmp_path, custom=tmp_path / "custom")
    return pages.Env(paths, "ar", None, "P", "demo", {})


def test_plug_key_follows_the_chosen_channel_preset(tmp_path, monkeypatch):
    monkeypatch.setenv("VEDIT_CONFIG_DIR", str(tmp_path / "cfg"))
    (tmp_path / "project.yaml").write_text("channel: ch\n")
    d = tmp_path / "cfg" / "channels" / "ch" / "plug"
    d.mkdir(parents=True)
    (d / "plug.yaml").write_text("name: A\n")
    pk = packs.load("base", [packs.BUILTIN])
    cue = Cue("p", "plug", "base", {}, "A", 10.0, 10.0, 28.0)
    cue.key = "k"
    pl = Placement(cue, 10.0, 18.0, 6)
    env = plug_env(tmp_path)
    assert pages.plug_dir(env) == d
    k1 = pages.key(pl, pk, env)
    (d / "plug.yaml").write_text("name: B\n")
    assert pages.key(pl, pk, env) != k1


def test_engine_key_covers_pack_module_and_doodles():
    names = {f.name for f in pages.ENGINE}
    assert {"pages.py", "pack.py", "spec.py", "scene.py"} <= names


def test_style_names_and_channel_are_validated(tmp_path, monkeypatch):
    monkeypatch.setenv("VEDIT_CONFIG_DIR", str(tmp_path / "cfg"))
    for bad in ("../foo", "A b", ""):
        with pytest.raises(VeditError):
            drafts.fork(bad, "x")
        with pytest.raises(VeditError):
            drafts.pick(bad, "x", "why")
        with pytest.raises(VeditError):
            drafts.save(bad, None, tmp_path, [], False)
    with pytest.raises(VeditError):
        drafts.pick("ok", "../x", "why")
    with pytest.raises(VeditError, match="--channel"):
        channel_of(SimpleNamespace(channel="../..", project=None))
    assert channel_of(SimpleNamespace(channel="ali-talks", project=None)) == "ali-talks"


def test_file_slots_stay_inside_the_project(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (tmp_path / "secret.html").write_text("x")
    (root / "ok.html").write_text("x")
    assert _inside(root, "ok.html") and not _inside(root, "../secret.html")
    f = root / "custom"
    f.mkdir()
    cue = Cue("c", "custom", "base", {"file": "../secret.html"}, "A", 1.0, 1.0, 5.0)
    paths = SimpleNamespace(root=root, custom=f)
    pk = packs.load("base", [packs.BUILTIN])
    with pytest.raises(VeditError, match="outside the project"):
        pages.render(Placement(cue, 1.0, 4.0, 6), pk, pages.Env(paths, "ar", None, None, "d", {}))


@pytest.mark.parametrize("acc", ["red", "#12", "javascript:1", "#GGGGGG"])
def test_project_accent_must_be_hex(tmp_path, acc):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.mov").write_bytes(b"")
    (tmp_path / "project.yaml").write_text(
        f"slug: d\nlang: ar\naccent: {json.dumps(acc)}\nsources:\n  A: {{ file: src/a.mov }}\n"
    )
    with pytest.raises(ProjectError, match="accent"):
        Project.load(tmp_path)
    (tmp_path / "project.yaml").write_text(
        "slug: d\nlang: ar\naccent: '#FFD60A'\nsources:\n  A: { file: src/a.mov }\n"
    )
    assert Project.load(tmp_path).accent == "#FFD60A"
