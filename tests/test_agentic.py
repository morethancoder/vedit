import json

import pytest

from vedit import cli, state
from vedit.commands import wait as waitcmd
from vedit.project import Paths


def test_every_command_declares_effects():
    allowed = {"reads", "writes", "renders", "model", "long", "destructive"}
    for verb in cli.COMMANDS:
        assert verb in cli.EFFECTS, f"{verb} has no EFFECTS entry"
        assert set(cli.EFFECTS[verb]) <= allowed and cli.EFFECTS[verb]


def test_commands_json_lists_every_command_with_flags(capsys):
    assert cli.main(["commands", "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["v"] == 1
    cmds = {c["name"]: c for c in d["data"]["commands"]}
    assert set(cmds) == set(cli.COMMANDS)
    wait = {f["name"]: f for f in cmds["wait"]["flags"]}
    assert wait["--timeout"]["type"] == "float" and wait["--events"]["type"] == "bool"
    out = {f["name"]: f for f in cmds["output"]["flags"]}
    assert out["action"]["choices"] == ["list", "add", "rm"] and out["action"]["positional"]
    assert cmds["clean"]["effects"] == ["destructive"] and cmds["render"]["guide"] == "vedit guide render"
    assert d["data"]["error_codes"]["busy"] == 3
    json.dumps(d)


def _proj(tmp_path):
    root = tmp_path / "p"
    (root / ".vedit").mkdir(parents=True)
    src = tmp_path / "a.mp4"
    src.write_bytes(b"x")
    (root / "project.yaml").write_text(f"slug: p\nlang: en\nsources:\n  A: {{ file: {src} }}\n")
    return root


def test_wait_no_job(tmp_path, capsys):
    root = _proj(tmp_path)
    assert cli.main(["wait", "--json", "--project", str(root)]) == 0
    assert json.loads(capsys.readouterr().out)["data"]["job"] is None


def test_wait_returns_job_result_and_streams_events(tmp_path, capsys, monkeypatch):
    root = _proj(tmp_path)
    paths = Paths(root)
    state.start_job(paths, "render", 4242, root / "log", chunk=1, chunks=2)
    seen = iter(["running", "running", "done"])
    monkeypatch.setattr(state, "job_state", lambda p: next(seen))
    monkeypatch.setattr(waitcmd, "POLL", 0)
    assert cli.main(["wait", "--events", "--json", "--project", str(root)]) == 0
    out = capsys.readouterr()
    events = [json.loads(ln) for ln in out.err.splitlines()]
    assert events[0]["stage"] == "render" and events[0]["chunk"] == 1 and events[-1]["state"] == "done"
    assert len(events) == 2  # unchanged progress is not repeated
    assert json.loads(out.out)["items"][0]["text"].startswith("render finished")


def test_wait_failed_job_exits_1(tmp_path, monkeypatch):
    root = _proj(tmp_path)
    state.start_job(Paths(root), "cut", 4242, root / "log")
    monkeypatch.setattr(state, "job_state", lambda p: "failed")
    assert cli.main(["wait", "--project", str(root)]) == 1


def test_wait_timeout_exits_124_with_code(tmp_path, capsys, monkeypatch):
    root = _proj(tmp_path)
    state.start_job(Paths(root), "render", 4242, root / "log")
    monkeypatch.setattr(state, "job_state", lambda p: "running")
    monkeypatch.setattr(waitcmd, "POLL", 0)
    assert cli.main(["wait", "--timeout", "0", "--json", "--project", str(root)]) == 124
    assert json.loads(capsys.readouterr().out)["code"] == "timeout"


@pytest.mark.parametrize("verb", sorted(set(cli.COMMANDS) - {"guide", "skill"}))
def test_help_works_for_every_command(verb, capsys):
    with pytest.raises(SystemExit) as e:
        cli.main([verb, "--help"])
    assert e.value.code == 0


def test_dry_run_is_rejected_where_not_supported(tmp_path, capsys):
    root = _proj(tmp_path)
    assert cli.main(["transcribe", "--dry-run", "--json", "--project", str(root)]) == 2
    assert json.loads(capsys.readouterr().out)["code"] == "usage"


def test_draft_dry_run_writes_nothing(tmp_path, capsys):
    root = _proj(tmp_path)
    h = root / ".vedit" / "hf"
    (h / "chunks").mkdir(parents=True)
    (h / "index.html").write_text("<html/>")
    for i in range(2):
        (h / "chunks" / f"chunk-{i:02d}.html").write_text(f"<html>{i}</html>")
    (h / "chunks.json").write_text(json.dumps({"bounds": [0, 4, 10], "total": 10, "mattes": {}}))
    before = sorted(str(p) for p in root.rglob("*"))
    assert cli.main(["draft", "--dry-run", "--json", "--project", str(root)]) == 0
    d = json.loads(capsys.readouterr().out)["data"]
    assert d == {"dry_run": True, "reuse_draft": False, "chunks": 2, "to_render": 2}
    assert sorted(str(p) for p in root.rglob("*")) == before
