import json

import numpy as np
import soundfile as sf

from vedit import studio
from vedit.cli import main
from vedit.cut import joins
from vedit.words import Edl


def words(text, t0=0.0, step=0.4):
    return [{"t0": t0 + i * step, "t1": t0 + i * step + 0.3, "w": w} for i, w in enumerate(text.split())]


# source words at 0.4 s steps; the cut removes 1.6-3.6 s (تجربة ... كثير), the join sits at program 1.6 s
SRC = words("هذا الفيديو راح يكون تجربة ويعني شيء اخر كثير ما كان عندي معرفة عن هذا الموضوع")
EDL = Edl(
    {
        "total": 4.0,
        "pieces": [
            {"clip": "A", "in": 0.0, "out": 1.6, "start": 0.0},
            {"clip": "A", "in": 3.6, "out": 7.2, "start": 1.6},
        ],
    }
)


def kinds(text):
    (j,) = joins.check(EDL, {"A": SRC}, words(text))
    return [f["kind"] for f in j["flags"]], j


def test_clean_join_has_no_flags():
    k, j = kinds("هذا الفيديو راح يكون ما كان عندي معرفة عن هذا الموضوع")
    assert k == [] and j["out"] == 1.6 and j["in"] == 3.6 and j["t"] == 1.6


def test_spelling_variants_do_not_fire():
    assert joins.sim(joins.norm("تيليغرام"), joins.norm("تلغرام")) >= joins.MATCH
    assert joins.sim(joins.norm("عضو"), joins.norm("أضو")) >= joins.MATCH
    assert joins.sim("رزق", "الرزق") == 1.0
    assert joins.sim("ما", "مو") == 0.0


def test_clipped_word():
    k, j = kinds("هذا الفيديو راح يك ما كان عندي معرفة عن هذا الموضوع")
    assert k == ["clipped"]
    assert j["flags"][0]["expected"] == "يكون" and j["flags"][0]["heard"] == "يك"


def test_dropped_negation_is_flagged():
    k, _ = kinds("هذا الفيديو راح يكون كان عندي معرفة عن هذا الموضوع")
    assert k == ["dropped"]


def test_removed_word_still_heard():
    src = words("اول شي ثم باليوتيوب ثانيا قناة جيدة")
    edl = Edl(
        {
            "pieces": [
                {"clip": "A", "in": 0, "out": 0.8, "start": 0},
                {"clip": "A", "in": 2.4, "out": 3.0, "start": 0.8},
            ]
        }
    )
    (j,) = joins.check(edl, {"A": src}, words("اول شي ثم باليوتيوب ثانيا جيدة"))
    assert {f["heard"] for f in j["flags"]} == {"باليوتيوب", "ثانيا"}
    (j,) = joins.check(edl, {"A": src}, words("اول شي جيدة"))
    assert j["flags"] == []


def test_garbled_run():
    k, _ = kinds("هذا الفيديو راح يكون ما بيتا كلمة معرفة عن هذا الموضوع")
    assert "garbled" in k


def test_ordinary_asr_drop_far_from_join_is_ignored():
    k, _ = kinds("الفيديو راح يكون ما كان عندي معرفة عن هذا الموضوع")
    assert k == []


def test_repeat_across_join():
    src = words("قلت شيء مهم جدا اليوم")
    edl = Edl(
        {
            "pieces": [
                {"clip": "A", "in": 0, "out": 1.2, "start": 0},
                {"clip": "A", "in": 1.6, "out": 2.4, "start": 1.2},
            ]
        }
    )
    (j,) = joins.check(edl, {"A": src}, words("قلت شيء مهم مهم جدا اليوم"))
    assert "repeat" in [f["kind"] for f in j["flags"]]


class FakeStudio:
    """Whole-program pass hears a clipped يك; the confirm pass (a wav named joins-confirm) hears `confirm`."""

    calls = 0
    confirm = "هذا الفيديو راح يك ما كان عندي معرفة عن"

    def __call__(self, path, lang, dialect=None, hint=None, **kw):
        FakeStudio.calls += 1
        text = self.confirm if "confirm" in path.name else "هذا الفيديو راح يك ما كان عندي معرفة عن"
        ws = [studio.Word(w["t0"], w["t1"], w["w"]) for w in words(text)]
        return studio.Transcript(ws, [], [], "fake", None, cached=False)


def make_project(tmp_path):
    root = tmp_path / "p"
    for d in ("media", "words", "edl", "program"):
        (root / ".vedit" / d).mkdir(parents=True)
    (root / "project.yaml").write_text("slug: p\nlang: ar\nsources:\n  A: {file: src/a.mp4}\n")
    (root / "src").mkdir()
    (root / "src" / "a.mp4").write_bytes(b"x")
    (root / ".vedit" / "words" / "A.json").write_text(json.dumps(SRC))
    (root / ".vedit" / "edl" / "edl.json").write_text(json.dumps({"total": 4.0, "pieces": EDL.pieces}))
    sf.write(root / ".vedit" / "program" / "program.wav", np.zeros(48000 * 5), 48000)
    return root


def test_command_wait_flags_and_caches(tmp_path, monkeypatch, capsys):
    root = make_project(tmp_path)
    FakeStudio.calls = 0
    monkeypatch.setattr(studio, "transcribe", FakeStudio())
    assert main(["joins", "--wait", "--project", str(root), "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["data"]["joins"] == 1 and d["data"]["flagged"] == 1
    assert d["data"]["results"][0]["flags"][0]["kind"] == "clipped"
    pw = json.loads((root / ".vedit" / "program" / "P.words.json").read_text())
    assert pw[0]["clip"] == "A" and "st" in pw[0]
    assert main(["joins", "--project", str(root)]) == 0  # cached: no detached job, no second Studio call
    assert (
        FakeStudio.calls == 3
    )  # program + confirm, then only confirm again (real Studio caches that by content)
    out = capsys.readouterr().out
    assert "1 joins, 1 flagged" in out and "expected:" in out and "heard:" in out and "‖" in out


def test_command_needs_a_built_program(tmp_path, capsys):
    root = make_project(tmp_path)
    (root / ".vedit" / "program" / "program.wav").unlink()
    assert main(["joins", "--wait", "--project", str(root)]) == 4  # not_built
    assert "next: vedit cut" in capsys.readouterr().err


def test_confirm_pass_drops_a_flag_the_excerpt_does_not_show(tmp_path, monkeypatch, capsys):
    root = make_project(tmp_path)
    fake = FakeStudio()
    fake.confirm = "هذا الفيديو راح يكون ما كان عندي معرفة عن"
    monkeypatch.setattr(studio, "transcribe", fake)
    assert main(["joins", "--wait", "--project", str(root), "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["data"]["joins"] == 1 and d["data"]["flagged"] == 0


def test_command_detaches_when_studio_is_needed(tmp_path, monkeypatch, capsys):
    from vedit.commands import joins as jc

    root = make_project(tmp_path)
    started = []

    class P:
        pid = 4242

    monkeypatch.setattr(jc.subprocess, "Popen", lambda cmd, **kw: started.append(cmd) or P())
    assert main(["joins", "--project", str(root)]) == 0
    assert started and "--wait" in started[0] and "joins" in started[0]
    assert "background" in capsys.readouterr().out
    st = json.loads((root / ".vedit" / "state.json").read_text())
    assert st["job"]["stage"] == "joins"
