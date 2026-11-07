import json
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from vedit import studio
from vedit.cli import main
from vedit.commands import listen as ls
from vedit.cut import splice

SR = 1000


def W(s, e, t):
    return studio.Word(s, e, t)


def ns(items, splice_=False, program=False):
    return SimpleNamespace(items=items, splice=splice_, program=program)


def test_cut_clamps_and_splice_piece_length():
    a = np.arange(10 * SR, dtype=np.float32)
    assert len(splice.cut(a, SR, -1, 2)) == 2 * SR
    assert len(splice.cut(a, SR, 9, 20)) == SR
    p = splice.splice_piece(a, SR, 4, 6)
    assert len(p) == int(3.6 * SR)
    assert p[0] == 2200 and p[int(1.8 * SR)] == 6000


def test_stitch_offsets_and_gap():
    p1, p2 = np.ones(1500, np.float32), np.ones(500, np.float32)
    audio, spans = splice.stitch([p1, p2], SR, gap=2.0)
    assert spans == [(0.0, 1.5), (3.5, 4.0)]
    assert len(audio) == 1500 + 2000 + 500 + 2000
    assert audio[1500:3500].sum() == 0


def test_assign_by_mid_time_to_local_times():
    spans = [(0.0, 1.5), (3.5, 4.0)]
    words = [W(0.1, 0.5, "a"), W(1.3, 1.6, "edge"), W(3.6, 3.9, "b"), W(2.0, 2.4, "gap")]
    got = splice.assign(words, spans)
    assert [w.text for w in got[0]] == ["a", "edge"]
    assert [w.text for w in got[1]] == ["b"]
    assert got[1][0].start == pytest.approx(0.1)


@pytest.fixture
def proj(tmp_path, monkeypatch):
    (tmp_path / "project.yaml").write_text(
        "slug: t\nlang: ar\ndialect: iq\nhint: Power\nsources:\n  A: { file: a.mp4 }\n"
    )
    (tmp_path / "a.mp4").write_bytes(b"x")
    media = tmp_path / ".vedit" / "media"
    media.mkdir(parents=True)
    sf.write(str(media / "A-48k.wav"), np.zeros(20 * SR, np.float32), SR)
    seen = {}

    def fake(wav, lang, dialect=None, hint=None, fillers="keep", vad=False, **kw):
        seen.update(wav=wav, lang=lang, dialect=dialect, hint=hint, fillers=fillers, vad=vad, **kw)
        seen["duration"] = sf.info(str(wav)).duration
        return studio.Transcript([W(1.0, 1.4, "هلا"), W(2.0, 2.5, "بيكم")], [], [], "m", None, False)

    monkeypatch.setattr(studio, "transcribe", fake)
    return tmp_path, seen


def test_listen_excerpt_prints_source_times(proj, capsys):
    root, seen = proj
    assert main(["listen", "A", "5", "12", "--project", str(root)]) == 0
    out = capsys.readouterr().out
    assert "6.00-6.40 هلا | 7.00-7.50 بيكم" in out
    assert seen["vad"] is False and seen["fillers"] == "keep" and seen["dialect"] == "iq"
    assert seen["hint"] == "Power"
    assert (root / ".vedit" / "listen" / "stamps.wav").is_file()


def test_listen_splice_one_line_each_json(proj, capsys):
    root, seen = proj
    assert main(["listen", "--splice", "A", "5:6", "A", "5:7", "--json", "--project", str(root)]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["data"]["mode"] == "splice"
    assert len(d["data"]["results"]) == 2
    # piece 1 is 3.6 s, then 2 s gap, piece 2 starts at 5.6: the fake words fall in piece 1 only
    assert d["data"]["results"][0]["text"] == "هلا بيكم"
    assert d["data"]["results"][1]["text"] == ""
    assert seen["duration"] == pytest.approx(3.6 + 2 + 3.6 + 2)


def test_listen_program_missing_says_cut(proj, capsys):
    root, _ = proj
    assert main(["listen", "--program", "412.5", "--project", str(root)]) == 4  # not_built
    err = capsys.readouterr().err
    assert "next: vedit cut" in err


def test_listen_program_reads_ranges(proj, capsys):
    root, seen = proj
    prog = root / ".vedit" / "program"
    prog.mkdir(parents=True)
    sf.write(str(prog / "program.wav"), np.zeros(20 * SR, np.float32), SR)
    assert main(["listen", "--program", "10", "3:4", "--json", "--project", str(root)]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["data"]["results"][0]["start"] == pytest.approx(7.8)
    assert d["data"]["results"][0]["end"] == pytest.approx(12.2)
    assert d["data"]["results"][1]["at"] == "3:4"
    assert seen["duration"] == pytest.approx(4.4 + 2.5 + 1.0 + 2.5)


def test_parse_errors():
    for bad in (
        ns(["A", "1"]),
        ns(["A", "x", "2"]),
        ns(["A", "5", "2"]),
        ns([], splice_=True),
        ns(["A"], True),
    ):
        with pytest.raises(ls.VeditError):
            ls.parse(bad)
    with pytest.raises(ls.VeditError):
        ls.parse(ns(["A", "5"], splice_=True))
    with pytest.raises(ls.VeditError):
        ls.parse(ns(["A", "9:3"], splice_=True))
    assert ls.parse(ns(["A", "1", "2"])) == ("excerpt", [("A", 1.0, 2.0)])
    assert ls.parse(ns(["B", "1:2"], splice_=True)) == ("splice", [("B", 1.0, 2.0)])
    assert ls.parse(ns(["1", "2:3"], program=True))[1][1] == ("2:3", 2.0, 3.0)


def test_unknown_clip(proj, capsys):
    root, _ = proj
    assert main(["listen", "Z", "1", "2", "--project", str(root)]) == 1
    assert "no clip 'Z'" in capsys.readouterr().err
