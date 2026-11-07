"""vedit styles: packs listed with scope, own/inherited types and problems; user packs from VEDIT_CONFIG_DIR."""

import json

import pytest

from vedit.cli import main
from vedit.commands import build


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    monkeypatch.setenv("VEDIT_CONFIG_DIR", str(tmp_path / "cfg"))
    return tmp_path / "cfg" / "styles"


def mk(root, name, text, types=()):
    d = root / name
    (d / "types").mkdir(parents=True)
    (d / "pack.yaml").write_text(text)
    for t in types:
        (d / "types" / f"{t}.html").write_text("<!-- vedit\nslots: {title: {}}\n-->\n<b>{{title}}</b>")
    return d


def test_styles_lists_builtin_and_user_packs(cfg, capsys):
    mk(cfg, "mine", "name: mine\nextends: yellow-doodle\nsummary: my look\n", types=["label"])
    assert main(["styles"]) == 0
    out = capsys.readouterr().out
    assert "▸ mine  (global)  my look" in out and "extends yellow-doodle" in out
    assert (
        "own types: label" in out and "from yellow-doodle: big-number" in out and "from base: custom" in out
    )
    assert "▸ yellow-doodle  (built-in)" in out and out.rstrip().splitlines()[-1].startswith("next: ")
    assert main(["styles", "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    mine = next(p for p in d["data"]["packs"] if p["name"] == "mine")
    assert (
        mine["scope"] == "global"
        and mine["own"] == ["label"]
        and mine["inherited"]["chip"] == "yellow-doodle"
    )
    assert mine["problems"] == [] and d["ok"] and d["next"]


def test_styles_reports_problems_and_shadowed_packs(cfg, capsys):
    mk(cfg, "yellow-doodle", "name: yellow-doodle\ncolours: {}\n")
    mk(cfg, "loop", "name: loop\nextends: nowhere\n")
    assert main(["styles", "--json"]) == 1
    d = json.loads(capsys.readouterr().out)
    rows = {(p["name"], p["scope"]): p for p in d["data"]["packs"]}
    assert "did you mean 'colors'" in rows[("yellow-doodle", "global")]["problems"][0]
    assert rows[("yellow-doodle", "built-in")]["hidden_by"] == "global"
    assert rows[("yellow-doodle", "built-in")]["problems"] == []
    assert "not found" in rows[("loop", "global")]["problems"][0]
    assert "vedit styles" in d["next"] and "loop" in d["next"]


def test_build_stops_on_a_broken_pack_listing_every_problem(cfg):
    mk(cfg, "bad", "name: bad\ncolours: {}\nfonts: [{family: X, file: nope.ttf}]\n")
    with pytest.raises(build.VeditError) as e:
        build.checked_pack("bad")
    assert "2 problem(s)" in e.value.message and "nope.ttf" in e.value.message
    assert build.checked_pack("yellow-doodle").name == "yellow-doodle"
