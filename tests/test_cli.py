import pytest

from vedit.cli import COMMANDS, main


def test_help_lists_every_command(capsys):
    with pytest.raises(SystemExit) as e:
        main(["--help"])
    assert e.value.code == 0
    out = capsys.readouterr().out
    for verb in COMMANDS:
        assert verb in out


def test_unbuilt_command_exits_2(capsys, monkeypatch):
    monkeypatch.setitem(COMMANDS, "review", (8, "snapshot sheet", None))  # every verb is built now
    assert main(["review"]) == 2
    assert "not built yet" in capsys.readouterr().err
