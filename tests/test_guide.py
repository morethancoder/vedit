import re

import pytest

from vedit import cli
from vedit.cli import COMMANDS, GUIDE_TOPIC, PLANNED_FLAGS, build_parser, main
from vedit.commands import guide, skill

CUE_TYPES = ["label", "chip", "kinetic", "big-number", "doodle", "screen", "chapter", "plug", "custom"]
TOPICS = [
    "agents",
    "formats",
    "ingest",
    "cuts",
    "drafts",
    "cues",
    "styles",
    "style-authoring",
    "channels",
    "review",
    "render",
    "traps",
    "errors",
]
BUDGET = {"overview": 60, "skill": 150}
WORD = r"[a-z]+(?:-[a-z]+)*"
# `vedit <verb> [<word>]` inside code spans/blocks, and any --flag; a trailing "-" or "<" means a placeholder.
CMD_RE = re.compile(rf"vedit ({WORD})(?![-\w])(?: ({WORD})(?![-\w]))?")
FLAG_RE = re.compile(r"(?<![\w-])--(?!vedit-)[a-z][a-z-]*")  # --vedit-* are CSS variables
CODE_RE = re.compile(r"```.*?```|`[^`\n]+`", re.DOTALL)


def pages() -> list[str]:
    return [*guide.topics(), "overview", "skill"]


GLOBAL_FLAGS = {"--json", "--project", "--yes", "--help"}
STYLE_SUBS = {"new", "try", "fork", "compare", "pick", "save"}


def flags_of(verb: str) -> set[str]:
    sp = next(a for a in build_parser()._actions if isinstance(a.choices, dict)).choices[verb]
    return {f for a in sp._actions for f in a.option_strings}


def valid_flags() -> set[str]:
    flags = {"--help", "--version"}
    parser = build_parser()
    for a in parser._actions:
        flags.update(a.option_strings)
        if hasattr(a, "choices") and isinstance(a.choices, dict):
            for sp in a.choices.values():
                for sa in sp._actions:
                    flags.update(sa.option_strings)
    for v in PLANNED_FLAGS.values():
        flags.update(v)
    return flags


def test_topic_set():
    assert set(guide.topics()) == set(TOPICS) | {f"cue-{c}" for c in CUE_TYPES}


@pytest.mark.parametrize("name", pages())
def test_page_budget(name):
    n = len(guide._dir().joinpath(f"{name}.md").read_text(encoding="utf-8").rstrip("\n").splitlines())
    assert n <= BUDGET.get(name, 150), f"{name}.md has {n} lines"


def test_rendered_overview_budget(capsys):
    assert main(["guide"]) == 0
    assert len(capsys.readouterr().out.rstrip("\n").splitlines()) <= 60


@pytest.mark.parametrize("name", pages())
def test_page_has_summary_and_names_real_commands(name):
    meta, body = guide.read_page(name)
    assert name == "skill" or meta.get("summary")
    flags = valid_flags()
    topics = set(guide.topics()) | {"--list"}
    for span in CODE_RE.findall(body):
        for verb, sub in CMD_RE.findall(span):
            assert verb in COMMANDS, f"{name}: unknown command 'vedit {verb}'"
            if verb == "guide" and sub:
                assert sub in topics, f"{name}: unknown guide topic '{sub}'"
            if verb == "skill" and sub:
                assert sub == "install", f"{name}: unknown skill action '{sub}'"
        for flag in FLAG_RE.findall(span):
            assert flag in flags, f"{name}: unknown flag {flag}"
    for line in body.splitlines():
        for m in re.finditer(rf"vedit ({WORD})(?![-\w])([^`]*)", line):
            verb, rest = m.groups()
            if verb not in COMMANDS:
                continue
            ok = flags_of(verb) | GLOBAL_FLAGS | set(PLANNED_FLAGS.get(verb, []))
            for flag in FLAG_RE.findall(rest):
                assert flag in ok, f"{name}: 'vedit {verb}' has no flag {flag}"
            if verb == "style":
                m2 = re.match(r" ([a-z]+(?:\|[a-z]+)*)", rest)
                if m2:
                    assert set(m2.group(1).split("|")) <= STYLE_SUBS, f"{name}: bad style sub {m2.group(1)}"
            if verb == "styles":
                m2 = re.match(r" ([a-z]+)", rest)
                assert not m2 or m2.group(1) in ("find", "show"), f"{name}: bad styles sub {m2.group(1)}"


def test_planned_flags_only_for_unbuilt_verbs():
    for verb in PLANNED_FLAGS:
        assert verb in COMMANDS and COMMANDS[verb][2] is None


def test_every_verb_has_a_real_guide_topic():
    for verb in COMMANDS:
        assert GUIDE_TOPIC[verb] in {"", *guide.topics()}


def test_loop_marks_unbuilt_from_table(monkeypatch):
    lines = guide.loop_lines()
    for verb in cli.LOOP:
        if verb.startswith("write "):
            continue
        line = next(ln for ln in lines if f"vedit {verb} " in ln)
        assert ("(not built yet)" in line) == (COMMANDS[verb][2] is None)
    patched = dict(COMMANDS, cut=(3, "x", "vedit.commands.status"))
    monkeypatch.setattr(cli, "COMMANDS", patched)
    assert "(not built yet)" not in next(ln for ln in guide.loop_lines() if "vedit cut " in ln)


def test_guide_overview_lists_files_and_topics(capsys):
    assert main(["guide"]) == 0
    out = capsys.readouterr().out
    assert "cuts.yaml" in out and "cues.yaml" in out and "custom/" in out and ".vedit/" in out
    assert "cue-label" in out and "next:" in out


def test_guide_topic_and_list(capsys):
    assert main(["guide", "cuts"]) == 0
    assert "# cuts.yaml" in capsys.readouterr().out
    assert main(["guide", "--list"]) == 0
    out = capsys.readouterr().out
    for t in guide.topics():
        assert t in out


def test_guide_json(capsys):
    import json

    assert main(["guide", "errors", "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["data"]["topic"] == "errors" and d["ok"]


def test_unknown_topic(capsys):
    assert main(["guide", "nope"]) == 1
    err = capsys.readouterr().err
    assert "vedit guide --list" in err


@pytest.mark.parametrize("verb", list(COMMANDS))
def test_help_short_with_guide_and_example(verb, capsys):
    with pytest.raises(SystemExit) as e:
        main([verb, "--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    # `output` carries a whole output spec as flags (kind, aspect, platforms, range, captions)
    assert len(out.splitlines()) <= {"output": 22}.get(verb, 20), out
    assert f"guide: vedit guide {GUIDE_TOPIC[verb]}".rstrip() in out
    assert "example: " in out


def test_unbuilt_text_has_next(capsys, monkeypatch):
    monkeypatch.setitem(cli.COMMANDS, "review", (8, "snapshot sheet", None))  # every verb is built now
    assert main(["review"]) == 2
    err = capsys.readouterr().err
    assert "not built yet (phase 08)" in err and "next: vedit guide review" in err


def test_unbuilt_json_is_one_value(capsys, monkeypatch):
    import json

    monkeypatch.setitem(cli.COMMANDS, "review", (8, "snapshot sheet", None))

    assert main(["review", "--json"]) == 2
    d = json.loads(capsys.readouterr().out)
    assert (
        d["ok"] is False
        and d["exit"] == 2
        and d["next"] == "vedit guide review"
        and "not built" in d["error"]
    )


def test_usage_error_json(capsys):
    import json

    with pytest.raises(SystemExit) as e:
        main(["nosuchverb", "--json"])
    assert e.value.code == 2
    d = json.loads(capsys.readouterr().out)
    assert d["ok"] is False and d["exit"] == 2


def test_skill_prints_skill(capsys):
    assert main(["skill"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("---\nname: vedit\ndescription:")
    assert "vedit guide" in out


def test_skill_install_writes_pointer(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert main(["skill", "install"]) == 0
    out = capsys.readouterr().out
    path = tmp_path / ".claude" / "skills" / "vedit" / "SKILL.md"
    text = path.read_text()
    assert len(text.splitlines()) <= 10 and text.startswith("---\nname: vedit")
    assert text != guide.read_page("skill")[1] and "AGENTS.md" in out
    assert main(["skill", "install"]) == 0  # same content: no prompt


def test_skill_install_refuses_other_file_without_yes(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    path = tmp_path / ".claude" / "skills" / "vedit" / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text("mine")
    assert main(["skill", "install"]) == 1
    assert "--yes" in capsys.readouterr().err and path.read_text() == "mine"
    assert main(["skill", "install", "--yes"]) == 0
    assert path.read_text() == skill.POINTER


def test_skill_pointer_budget():
    assert len(skill.POINTER.splitlines()) <= 10
