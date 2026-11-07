import json

from vedit.cli import main
from vedit.commands import clean
from vedit.project import Project


def build(tmp_path):
    proj = tmp_path / "proj"
    cap = tmp_path / "orig" / "Rec.cap"
    (cap / "output").mkdir(parents=True)
    (cap / "output" / "result.mp4").write_bytes(b"v" * 5000)
    (cap / "recording-meta.json").write_text(json.dumps({"pretty_name": "My Talk"}))
    rec = tmp_path / "recs"
    twin = rec / "twin.cap"
    twin.mkdir(parents=True)
    (twin / "recording-meta.json").write_text(json.dumps({"pretty_name": "My Talk"}))
    other = rec / "other.cap"
    other.mkdir()
    (other / "recording-meta.json").write_text(json.dumps({"pretty_name": "Else"}))
    (proj / "src").mkdir(parents=True)
    (proj / "src" / "A.mp4").symlink_to(cap / "output" / "result.mp4")
    (proj / "project.yaml").write_text(f"slug: t\nlang: ar\nsources:\n  A: {{ cap: {cap} }}\n")
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
    return proj, cap, twin, other, rec, gone_always, gone_posted, kept


def test_clean_always_keeps_the_keep_set(tmp_path, capsys):
    proj, cap, _t, _o, _r, ga, gp, kept = build(tmp_path)
    assert main(["clean", "--project", str(proj), "--json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["data"]["freed_bytes"] > 0
    assert not any(f.exists() for f in ga)
    assert all(f.exists() for f in gp + kept)
    assert cap.exists()


def test_posted_dry_run_lists_and_deletes_nothing(tmp_path, capsys):
    proj, cap, _t, _o, _r, ga, gp, kept = build(tmp_path)
    assert main(["clean", "--posted", "--dry-run", "--project", str(proj)]) == 0
    out = capsys.readouterr().out
    assert "master.mp4" in out or "renders" in out
    assert str(cap) in out
    assert all(f.exists() for f in ga + gp + kept) and cap.exists()


def test_posted_without_tty_or_yes_deletes_nothing(tmp_path, capsys, monkeypatch):
    proj, cap, _t, _o, _r, ga, gp, kept = build(tmp_path)
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False, raising=False)
    assert main(["clean", "--posted", "--project", str(proj)]) == 0
    assert "--yes" in capsys.readouterr().out
    assert all(f.exists() for f in ga + gp + kept) and cap.exists()


def test_posted_yes_removes_originals_and_keeps_edit(tmp_path, monkeypatch):
    proj, cap, twin, other, rec, ga, gp, kept = build(tmp_path)
    monkeypatch.setattr(clean, "CAP_RECORDINGS", rec)
    monkeypatch.setattr(clean, "find_caps", lambda p, recordings=rec, _f=clean.find_caps: _f(p, rec))
    assert main(["clean", "--posted", "--yes", "--project", str(proj)]) == 0
    assert not any(f.exists() for f in ga + gp)
    assert all(f.exists() for f in kept)
    assert not cap.exists() and not twin.exists()  # matched by pretty_name
    assert other.exists()  # different pretty_name
    assert not (proj / "src" / "A.mp4").is_symlink()


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


def test_find_caps_by_pretty_name(tmp_path):
    proj, cap, twin, _o, rec, *_ = build(tmp_path)
    caps = clean.find_caps(Project.load(proj), rec)
    assert set(caps) == {cap.resolve(), twin.resolve()}
