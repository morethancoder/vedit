import json
import subprocess

import pytest

from vedit import state, studio
from vedit.cli import main
from vedit.commands import transcribe as tr
from vedit.project import Project


def W(s, e, t):
    return studio.Word(s, e, t)


@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.delenv("VEDIT_JOB", raising=False)
    src = tmp_path / "a.mp4"
    src.write_bytes(b"x" * 10)
    (tmp_path / "project.yaml").write_text(
        f"slug: t\nlang: ar\ndialect: iq\nhint: Power\nsources:\n  A: {{ file: {src} }}\n"
    )
    p = Project.load(tmp_path)
    p.paths.ensure()
    (p.paths.media / "A-48k.wav").write_bytes(b"RIFF" + b"0" * 100)
    return p


@pytest.fixture
def calls(monkeypatch):
    seen = []

    def fake(wav, lang, dialect=None, hint=None, fillers="keep", **kw):
        seen.append((wav.name, lang, dialect, hint, fillers))
        words = [W(0.0, 0.4, "هلا"), W(0.5, 0.9, "بيكم."), W(2.5, 3.0, "شلونكم")]
        return studio.Transcript(words, [], ["warn1"], "qwen3-asr-1.7b", None, False)

    monkeypatch.setattr(studio, "transcribe", fake)
    return seen


def go(proj, *a):
    return main(["transcribe", "--project", str(proj.root), *a])


def test_wait_writes_words_and_txt(proj, calls, capsys):
    assert go(proj, "--wait") == 0
    out = capsys.readouterr().out
    assert calls == [("A-48k.wav", "ar", "iq", "Power", "keep")]
    ws = json.loads((proj.paths.words / "A.json").read_text(encoding="utf-8"))
    assert ws[0] == {"t0": 0.0, "t1": 0.4, "w": "هلا"} and len(ws) == 3
    txt = (proj.paths.words / "A.txt").read_text(encoding="utf-8").splitlines()
    assert txt == ["00:00.00–00:00.90  هلا بيكم.", "00:02.50–00:03.00  شلونكم"]
    assert "3 words" in out and "warn1" in out and "next: vedit summarize" in out
    assert state.stage_status(proj, proj.paths)["transcribe"] == "done"


def test_second_run_skips_studio_and_force_redoes(proj, calls, monkeypatch):
    go(proj, "--wait")
    go(proj, "--wait")
    assert len(calls) == 1
    # also instant without --wait: nothing to do, so nothing is spawned
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("spawned"))
    assert go(proj) == 0 and len(calls) == 1
    go(proj, "--wait", "--force")
    assert len(calls) == 2


def test_detached_spawns_and_starts_job(proj, calls, monkeypatch, capsys):
    popen = {}

    class P:
        pid = 4242

    def fake(cmd, **kw):
        popen.update(cmd=cmd, **kw)
        return P()

    monkeypatch.setattr(subprocess, "Popen", fake)
    assert go(proj, "--force") == 0
    assert calls == []
    assert popen["cmd"][1:5] == ["-m", "vedit", "transcribe", "--wait"] and "--force" in popen["cmd"]
    assert popen["start_new_session"] is True and popen["stdin"] == subprocess.DEVNULL
    job = state.load(proj.paths)["job"]
    assert job["pid"] == 4242 and job["stage"] == "transcribe" and job["progress"] == {"clips": 1, "clip": 0}
    assert "next: vedit status" in capsys.readouterr().out


def test_already_running_guard(proj, calls, monkeypatch, capsys):
    import os

    state.start_job(proj.paths, "transcribe", os.getpid(), "log", clips=1, clip=0)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: pytest.fail("spawned"))
    assert go(proj) == 0
    assert "already running" in capsys.readouterr().out


def test_child_updates_progress_and_finishes(proj, calls, monkeypatch):
    monkeypatch.setenv("VEDIT_JOB", "1")
    state.start_job(proj.paths, "transcribe", 1, "log", clips=1, clip=0)
    go(proj, "--wait")
    job = state.load(proj.paths)["job"]
    assert job["status"] == "done" and job["progress"]["clip"] == 1


def test_child_failure_finishes_failed(proj, monkeypatch):
    monkeypatch.setenv("VEDIT_JOB", "1")
    state.start_job(proj.paths, "transcribe", 1, "log", clips=1, clip=0)

    def boom(*a, **k):
        raise studio.StudioError("no model")

    monkeypatch.setattr(studio, "transcribe", boom)
    assert go(proj, "--wait") == 1
    assert state.load(proj.paths)["job"]["status"] == "failed"


def test_missing_wav(proj, calls, capsys):
    (proj.paths.media / "A-48k.wav").unlink()
    assert go(proj, "--wait") == 4  # not_built
    err = capsys.readouterr().err
    assert "A-48k.wav" in err and "next: vedit new" in err


def test_lines_break_on_gap_punct_and_max():
    ws = [{"t0": i * 0.1, "t1": i * 0.1 + 0.05, "w": "a"} for i in range(40)]
    assert [len(g) for g in tr.lines(ws)] == [18, 18, 4]


def test_mixed_script_warns_and_survives_cache(proj, monkeypatch, capsys):
    def fake(wav, lang, dialect=None, hint=None, fillers="keep", **kw):
        words = [W(0.16, 0.4, "سalam"), W(0.5, 0.9, "hello"), W(1.0, 1.2, "مرحباk")]
        return studio.Transcript(words, [], [], "m", None, False)

    monkeypatch.setattr(studio, "transcribe", fake)
    assert go(proj, "--wait") == 0
    out = capsys.readouterr().out
    assert "2 mixed Arabic/Latin" in out and "A 0.16 سalam" in out
    go(proj, "--wait")  # cache hit keeps the warning
    out = capsys.readouterr().out
    assert "cached" in out and "A 0.16 سalam" in out
    go(proj, "--wait", "--json")
    clip = json.loads(capsys.readouterr().out)["data"]["clips"][0]
    assert clip["mixed_script"] == [{"t": 0.16, "w": "سalam"}, {"t": 1.0, "w": "مرحباk"}]


def test_mixed_script_truncates_list():
    from vedit.report import Report

    r = Report("t")
    tr._warn_mixed(r, "A", [{"t": i, "w": "سa"} for i in range(11)])
    assert "11 mixed" in r.items[-1]["text"] and "and 3 more" in r.items[-1]["text"]
