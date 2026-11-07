import json

from vedit.cli import main
from vedit.commands import clean
from vedit.project import Project


def build(tmp_path):
    """A project whose source came through an importer: origin = the recorder's project folder, the edited
    video inside it, plus an export copy outside it (kept)."""
    proj = tmp_path / "proj"
    orig = tmp_path / "orig" / "Rec.myrec"
    (orig / "output").mkdir(parents=True)
    (orig / "output" / "result.mp4").write_bytes(b"v" * 5000)
    rec = tmp_path / "recs"
    twin = rec / "twin.myrec"
    twin.mkdir(parents=True)
    other = rec / "other.myrec"
    other.mkdir()
    export = tmp_path / "exports" / "My Talk.mp4"
    export.parent.mkdir()
    export.write_bytes(b"e" * 100)
    (proj / "src").mkdir(parents=True)
    (proj / "src" / "A.mp4").symlink_to(orig / "output" / "result.mp4")
    (proj / "src" / "B.mp4").symlink_to(export)
    (proj / "project.yaml").write_text(
        f"slug: t\nlang: ar\nsources:\n  A: {{ file: src/A.mp4, origin: {orig}, importer: myrec }}\n"
        f"  B: {{ file: src/B.mp4, origin: {orig}, importer: myrec }}\n"
    )
    v = proj / ".vedit"
    gone_always = [
        v / "cache/frames/x.png",
        v / "renders/chunks/c0.mp4",
        v / "tmp/s.jpg",
        v / "listen/a.wav",
        v / "build/snaps-1/a.png",
        v / "build/tcmp/b.png",
    ]
    gone_posted = [
        v / "renders/master.mp4",
        v / "media/A-cam.mp4",
        v / "program/proxy.mp4",
        v / "mattes/m.webm",
    ]
    kept = [
        proj / "cuts.yaml",
        proj / "cues.yaml",
        proj / "custom/a.txt",
        proj / "subs/ar.srt",
        proj / "youtube/t.txt",
        proj / "summary.md",
        v / "words/A.json",
        v / "studio/A.json",
        v / "edl/e.json",
        v / "logs/l.log",
        v / "listen/notes.txt",
        v / "build/lum.json",
    ]
    for f in gone_always + gone_posted + kept:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"data" * 100)
    return proj, orig, twin, other, rec, gone_always, gone_posted, kept


def test_clean_always_keeps_the_keep_set(tmp_path, capsys):
    proj, orig, _t, _o, _r, ga, gp, kept = build(tmp_path)
    assert main(["clean", "--project", str(proj), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["data"]["freed_bytes"] > 0
    assert not any(f.exists() for f in ga)
    assert all(f.exists() for f in gp + kept)
    assert orig.exists()


def test_posted_dry_run_lists_and_deletes_nothing(tmp_path, capsys):
    proj, orig, _t, _o, _r, ga, gp, kept = build(tmp_path)
    assert main(["clean", "--posted", "--dry-run", "--project", str(proj)]) == 0
    out = capsys.readouterr().out
    assert "master.mp4" in out or "renders" in out
    assert str(orig) in out
    assert all(f.exists() for f in ga + gp + kept) and orig.exists()


def test_posted_without_tty_or_yes_deletes_nothing(tmp_path, capsys, monkeypatch):
    proj, orig, _t, _o, _r, ga, gp, kept = build(tmp_path)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    assert main(["clean", "--posted", "--project", str(proj)]) == 0
    assert "--yes" in capsys.readouterr().out
    assert all(f.exists() for f in ga + gp + kept) and orig.exists()


def test_posted_yes_removes_originals_and_keeps_edit(tmp_path, monkeypatch):
    proj, orig, twin, other, _rec, ga, gp, kept = build(tmp_path)
    plugin = tmp_path / "cfgp" / "importers"
    plugin.mkdir(parents=True)
    (plugin / "myrec.py").write_text(
        "from pathlib import Path\n"
        f"def read(p): return None\n"
        f"def originals(o): return [(Path(o), 'rec'), (Path({str(twin)!r}), 'twin')], []\n"
    )
    monkeypatch.setenv("VEDIT_CONFIG_DIR", str(plugin.parent))
    export = (proj / "src" / "B.mp4").resolve()
    assert main(["clean", "--posted", "--yes", "--project", str(proj)]) == 0
    assert not any(f.exists() for f in ga + gp)
    assert all(f.exists() for f in kept)
    assert not orig.exists() and not twin.exists()  # the importer's originals()
    assert other.exists() and export.exists()  # not named / outside the recording project: kept
    assert not (proj / "src" / "A.mp4").is_symlink()


def test_origin_without_its_importer_is_listed_alone(tmp_path):
    proj, orig, twin, *_ = build(tmp_path)
    dele, kept = clean.original_targets(Project.load(proj))
    assert [p for p, _ in dele] == [orig.resolve()] and twin.exists()
    assert kept == [(proj / "src" / "B.mp4").resolve()]


def test_refuses_while_job_runs(tmp_path, monkeypatch, capsys):
    proj, *_ = build(tmp_path)
    monkeypatch.setattr("vedit.state.job_state", lambda p: "running")
    assert main(["clean", "--project", str(proj)]) == 3  # busy
    assert "job is running" in capsys.readouterr().err


def test_disk_bytes_counts_hardlink_once(tmp_path):
    a = tmp_path / "a"
    a.write_bytes(b"x" * 100000)
    (tmp_path / "b").hardlink_to(a)
    assert clean.disk_bytes(tmp_path) < 2 * clean.disk_bytes(a)
