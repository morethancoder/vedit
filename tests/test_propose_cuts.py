import json

import pytest
import yaml

from vedit import llm, state
from vedit.cli import main
from vedit.commands import propose_cuts as pc
from vedit.project import Project

TEXT = "سلام عليكم راح راح أتكلم يعني عن البوت ما اشتغل من 200 ألف عضو PowerTeleBot هو المنصة"
WORDS = [{"t0": i * 0.5, "t1": i * 0.5 + 0.4, "w": w} for i, w in enumerate(TEXT.split())]
CUTS = [
    {"near": "A 0.0", "say": "راح", "why": "stutter"},  # `near` = the line start, as the model sees it
    {"near": "A 0.0", "say": "يعني", "why": "filler"},
    {"near": "[A 0.0]", "say": "ما", "why": "filler"},  # a negation: risky
    {"near": "A 0.0", "say": "راح راح", "why": "overlap"},  # overlaps the first: dropped
]


@pytest.fixture
def proj(tmp_path):
    src = tmp_path / "a.mp4"
    src.write_bytes(b"x")
    (tmp_path / "project.yaml").write_text(
        f"slug: t\nlang: ar\nhint: PowerTeleBot, MCP\nsources:\n  A: {{ file: {src} }}\n"
    )
    p = Project.load(tmp_path)
    p.paths.ensure()
    (p.paths.words / "A.json").write_text(json.dumps(WORDS, ensure_ascii=False), encoding="utf-8")
    (tmp_path / "cuts.yaml").write_text("cuts: []\n")
    return p


def reply(cuts):
    return json.dumps({"cuts": cuts}, ensure_ascii=False)


@pytest.fixture
def model(monkeypatch):
    queue, seen = [reply(CUTS)], []

    def fake(mid, text, effort, timeout):
        seen.append(mid)
        return llm.Reply(queue.pop(0) if queue else reply(CUTS), mid, 100, 50, 0.05)

    monkeypatch.setitem(llm.BACKENDS, "claude", fake)
    return queue, seen


def w(*toks):
    return [{"t0": i, "t1": i + 0.5, "w": t} for i, t in enumerate(toks)]


def test_risks():
    names = {"powertelebot"}
    assert pc.risks(w("يعني"), names) == []
    assert pc.risks(w("ما"), names) == ["negation ما"]
    assert pc.risks(w("من", "200"), names) == ["number 200"]
    assert pc.risks(w("وعشرين"), names) == ["number وعشرين"]
    assert pc.risks(w("PowerTeleBot"), names) == ["name PowerTeleBot"]
    assert pc.risks(w("خلت", "بعد"), names, "هذا", "ما")[0].startswith("join: negation ما")
    assert pc.risks(w("الحمد"), names, "وتمت", "لله") == ["join: leaves لله torn from its phrase"]
    assert pc.risks(w("عالي"), names, "أنا", "بخرج") == ["cut right after أنا: a name?"]
    long = pc.risks(w(*["كلمة"] * 9), names)
    assert long and long[0].startswith("long: 9 words")


def test_match_drops_misses_and_overlaps():
    found, missed = pc.match([*CUTS, {"near": "A 3.0", "say": "مو موجود", "why": "x"}], {"A": WORDS})
    assert [c["say"] for c in found] == ["راح", "يعني", "ما"]
    assert {m["say"] for m in missed} == {"راح راح", "مو موجود"}
    assert [c["span"].i0 for c in found] == [2, 5, 8] and found[0]["span"].clip == "A"


def test_match_second_line_and_time_fallback():
    found, _ = pc.match(
        [{"near": "A 0.0", "say": "PowerTeleBot", "why": "x"}, {"near": "A 7.4", "say": "هو", "why": "y"}],
        {"A": WORDS},
    )
    assert [c["span"].i0 for c in found] == [14, 15]  # next line; then plain search near 6.4 s


def test_writes_proposed_never_cuts_yaml(proj, model, capsys):
    assert main(["propose-cuts", "--project", str(proj.root)]) == 0
    out = capsys.readouterr().out
    assert model[1] == ["claude-sonnet-5-5"]
    assert (proj.root / "cuts.yaml").read_text() == "cuts: []\n"
    text = (proj.root / "cuts.proposed.yaml").read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    assert [c["say"] for c in data["cuts"]] == ["ما", "راح", "يعني"]  # risky first, then time order
    assert data["cuts"][0]["near"] == "A 4.0"
    assert "# RISKY: negation ما" in text and "[ما]" in text
    assert "# REPEAT:" not in text  # "راح راح" is a stutter: words.find resolves it to the first copy
    assert "3 cuts" in out and "1 risky first" in out and "overlaps an earlier cut" in out
    assert state.load(proj.paths)["stages"]["propose-cuts"]["outputs"] == [
        str(proj.root / "cuts.proposed.yaml")
    ]


def test_too_many_misses_retry(proj, model):
    queue, seen = model
    queue[:] = [
        reply([{"near": "A 1", "say": "غلط", "why": "x"}, {"near": "A 2", "say": "غلط2", "why": "x"}])
    ]
    assert main(["propose-cuts", "--project", str(proj.root)]) == 0
    assert len(seen) == 2
    log = [json.loads(x) for x in (proj.paths.logs / "llm.jsonl").read_text().splitlines()]
    assert not log[0]["ok"] and "do not match the transcript" in log[0]["error"]


def test_cached_until_forced(proj, model, capsys):
    main(["propose-cuts", "--project", str(proj.root)])
    assert main(["propose-cuts", "--project", str(proj.root), "--json"]) == 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["data"]["cached"] is True
    main(["propose-cuts", "--project", str(proj.root), "--force"])
    assert len(model[1]) == 2
