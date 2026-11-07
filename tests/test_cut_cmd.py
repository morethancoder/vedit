import json

import numpy as np
import soundfile as sf

from vedit.cli import main
from vedit.commands import cut as cutcmd

SR = 48000


def make_project(tmp_path, cuts_text):
    root = tmp_path / "p"
    (root / ".vedit" / "media").mkdir(parents=True)
    (root / ".vedit" / "words").mkdir()
    (root / "project.yaml").write_text("slug: p\nlang: ar\nsources:\n  A: {file: src/a.mp4}\n")
    (root / "src").mkdir()
    (root / "src" / "a.mp4").write_bytes(b"x")
    rng = np.random.default_rng(1)
    a = rng.normal(0, 0.1, SR * 8)
    a[SR * 3 : SR * 4] = 0  # a 1 s silence
    sf.write(root / ".vedit" / "media" / "A-48k.wav", np.stack([a, a], 1), SR)
    words = [
        {"t0": float(i), "t1": i + 0.5, "w": w}
        for i, w in enumerate(["one", "two", "three", "four", "five", "six"])
    ]
    (root / ".vedit" / "words" / "A.json").write_text(json.dumps(words))
    (root / "cuts.yaml").write_text(cuts_text)
    return root


def test_cut_wait_edl_only_writes_edl_and_records_stage(tmp_path, capsys):
    root = make_project(tmp_path, "cuts:\n  - {near: A 1.0, say: two}\nend: last-word\n")
    assert main(["cut", "--wait", "--edl-only", "--no-listen", "--project", str(root)]) == 0
    e = json.loads((root / ".vedit" / "edl" / "edl.json").read_text())
    assert e["pieces"] and e["fade_start"] == 3.9666  # program time of the last word end (5.5 in the source)
    assert (root / ".vedit" / "edl" / "envelope-A.npy").is_file()
    assert json.loads((root / ".vedit" / "edl" / "cuts.json").read_text())["cuts"][0]["label"] == "two"
    assert "cut" in json.loads((root / ".vedit" / "state.json").read_text())["stages"]
    assert "program" in capsys.readouterr().out


def test_unresolved_cut_fails_with_the_list(tmp_path, capsys):
    root = make_project(tmp_path, "cuts:\n  - {near: A 1.0, say: nonsense}\n")
    assert main(["cut", "--wait", "--edl-only", "--project", str(root)]) == 1
    err = capsys.readouterr().err
    assert "did not resolve" in err and "nonsense" in err and "next:" in err


def test_envelope_cache_is_keyed_by_wav(tmp_path):
    root = make_project(tmp_path, "end: last-word\n")
    from vedit.project import Project

    paths = Project.load(root).paths
    wav = paths.media / "A-48k.wav"
    a = cutcmd.get_envelope(paths, "A", wav)
    assert np.array_equal(a, cutcmd.get_envelope(paths, "A", wav))
    sf.write(wav, np.zeros((SR * 2, 2)), SR)
    assert len(cutcmd.get_envelope(paths, "A", wav)) == 200


def test_cut_with_listening_logs_and_reports_progress(tmp_path, monkeypatch):
    # regression: the refine hook got the log *path* and a one-arg step; it crashed whenever a cut was not cached
    from vedit.cut import splice

    root = make_project(tmp_path, "fillers: false\ncuts:\n  - {near: A 1.0, say: two}\nend: last-word\n")
    monkeypatch.setattr(
        splice, "listen", lambda project, pieces, sr, **k: [[splice.Heard(0, 0.1, "one")] for _ in pieces]
    )
    assert main(["cut", "--wait", "--edl-only", "--project", str(root)]) == 0
    assert "listening to" in (root / ".vedit" / "logs" / "cut.log").read_text()
    assert json.loads((root / ".vedit" / "edl" / "refined.json").read_text())
