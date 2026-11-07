import json

import pytest

from vedit import llm, state
from vedit.cli import main
from vedit.commands import summarize as sm
from vedit.project import Project

WORDS = [
    {"t0": 0.2, "t1": 0.6, "w": "سلام"},
    {"t0": 0.7, "t1": 1.1, "w": "عليكم"},
    {"t0": 5.0, "t1": 5.5, "w": "من"},
    {"t0": 5.6, "t1": 6.0, "w": "200"},
    {"t0": 6.1, "t1": 6.5, "w": "ألف"},
]
REPLY = {
    "chapters": [
        {"start": "[A 0.2]", "title": "مقدمة", "about": "Intro.", "beats": [{"at": "A 5.0", "text": "200K"}]}
    ],
    "visual_moments": [{"at": "5.0", "kind": "number", "show": "200K", "words": "من 200 ألف"}],
    "asr_errors": [],
    "terms": [{"term": "Power", "note": "his product"}],
}


@pytest.fixture
def proj(tmp_path):
    src = tmp_path / "a.mp4"
    src.write_bytes(b"x")
    (tmp_path / "project.yaml").write_text(
        f"slug: t\nlang: ar\nhint: Power\nsources:\n  A: {{ file: {src} }}\n"
    )
    p = Project.load(tmp_path)
    p.paths.ensure()
    (p.paths.words / "A.json").write_text(json.dumps(WORDS, ensure_ascii=False), encoding="utf-8")
    return p


@pytest.fixture
def model(monkeypatch):
    seen = []

    def fake(mid, text, effort, timeout):
        seen.append((mid, text))
        return llm.Reply(json.dumps(REPLY, ensure_ascii=False), mid, 100, 50, 0.002)

    monkeypatch.setitem(llm.BACKENDS, "claude", fake)
    return seen


def test_fix_at():
    clips = {"A": 10.0}
    assert sm.fix_at("[A 1.25]", clips) == "A 1.2" or sm.fix_at("[A 1.25]", clips) == "A 1.3"
    assert sm.fix_at("3", clips) == "A 3.0"
    assert sm.fix_at("A 4s", clips) == "A 4.0"
    for bad in ("B 1.0", "A 99", "soon"):
        with pytest.raises(llm.Invalid):
            sm.fix_at(bad, clips)


def test_writes_summary_md_on_haiku(proj, model, capsys):
    assert main(["summarize", "--project", str(proj.root)]) == 0
    out = capsys.readouterr().out
    assert model[0][0] == "claude-haiku-5-5"
    assert "[A 0.2] سلام عليكم" in model[0][1] and "Names and terms that occur: Power." in model[0][1]
    md = proj.paths.summary.read_text(encoding="utf-8")
    assert "### 1. مقدمة  (A 0.2)" in md and "- A 5.0  200K" in md
    assert '- A 5.0  **number**: 200K  ("من 200 ألف")' in md and "- none spotted" in md
    assert "1 chapters, 1 visual moments" in out and "next: write cuts.yaml" in out
    assert state.load(proj.paths)["stages"]["summarize"]["outputs"] == [str(proj.paths.summary)]
    log = [json.loads(x) for x in (proj.paths.logs / "llm.jsonl").read_text().splitlines()]
    assert log[-1]["ok"] and log[-1]["model"] == "haiku"


def test_cached_until_forced(proj, model, capsys):
    main(["summarize", "--project", str(proj.root)])
    assert main(["summarize", "--project", str(proj.root)]) == 0
    assert len(model) == 1 and "up to date" in capsys.readouterr().out
    main(["summarize", "--project", str(proj.root), "--force"])
    assert len(model) == 2


def test_bad_times_are_retried(proj, monkeypatch):
    replies = [{**REPLY, "asr_errors": [{"at": "A 500", "heard": "x", "likely": "y"}]}, REPLY]
    monkeypatch.setitem(
        llm.BACKENDS, "claude", lambda mid, *a: llm.Reply(json.dumps(replies.pop(0), ensure_ascii=False), mid)
    )
    assert main(["summarize", "--project", str(proj.root)]) == 0
    assert not replies


def test_needs_transcript(proj, model, capsys):
    (proj.paths.words / "A.json").unlink()
    assert main(["summarize", "--project", str(proj.root)]) == 1
    assert "next: vedit transcribe" in capsys.readouterr().err
