import json

import pytest

from vedit import cli
from vedit.report import Report, VeditError, confirm


def test_text_and_json_shapes():
    r = Report("demo")
    r.step("s").ok_("fine").warn("hmm").info("note")
    r.next = "vedit cut"
    assert r.ok
    t = r.to_text(color=False)
    assert "▸ s" in t and "✓ fine" in t and "! hmm" in t and t.endswith("next: vedit cut")
    assert "\033" in r.to_text(color=True)
    r.fail("bad")
    d = r.to_dict()
    assert (
        not r.ok
        and d["ok"] is False
        and set(d) == {"v", "command", "ok", "artifacts", "items", "data", "next"}
    )
    json.dumps(d)


def test_confirm(monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    assert confirm("q", yes=True)
    assert not confirm("q")  # pytest stdin is not a TTY
    monkeypatch.setenv("CI", "1")
    assert confirm("q") and not confirm("q", destructive=True)


def test_cli_json_error(monkeypatch, capsys):
    class Mod:
        @staticmethod
        def run(ns):
            raise VeditError("boom", next="vedit doctor", exit=3)

    monkeypatch.setitem(cli.COMMANDS, "doctor", (1, "x", "m"))
    monkeypatch.setattr(cli, "_module", lambda verb: Mod)
    assert cli.main(["doctor", "--json"]) == 3
    out = capsys.readouterr().out
    assert json.loads(out) == {
        "v": 1,
        "ok": False,
        "error": "boom",
        "code": "failed",
        "next": "vedit doctor",
        "exit": 3,
    }
    assert cli.main(["doctor"]) == 3
    err = capsys.readouterr().err
    assert "error: boom" in err and "next: vedit doctor" in err


def test_unused():
    pytest.importorskip("json")


def test_error_codes_map_to_exits_and_are_inferred():
    from vedit.report import CODES, infer_code

    assert (
        CODES["busy"] == 3 and CODES["not_built"] == 4 and CODES["no_disk"] == 5 and CODES["timeout"] == 124
    )
    assert VeditError("x", code="busy").exit == 3
    assert VeditError("x", exit=2).code == "usage"
    assert VeditError("boom").code == "failed" and VeditError("boom").exit == 1
    assert infer_code("/p/edl.json is not built yet", "vedit cut", None) == "not_built"
    assert infer_code("not enough disk: 3 GB free", None, None) == "no_disk"
    assert infer_code("a cut job is already running (pid 4)", None, None) == "busy"
    assert infer_code("studio timed out after 30s", None, None) == "timeout"
    assert infer_code("style 'nope' not found", None, None) == "bad_input"
    with pytest.raises(ValueError):
        VeditError("x", code="nope")


def test_run_maps_tool_exits_to_codes(tmp_path):
    from vedit.run import RunError, run

    with pytest.raises(RunError) as e:
        run(["definitely-not-a-tool-xyz"], 10)
    assert e.value.code == "missing_tool" and e.value.exit == 5


def test_report_lists_artifacts():
    r = Report("x").artifact("/p/a.mp4", "video")
    assert r.to_dict()["artifacts"] == [{"path": "/p/a.mp4", "kind": "video"}] and r.to_dict()["v"] == 1
