import json
import shutil
from pathlib import Path

import pytest
import yaml

from vedit import channel as chan
from vedit.cli import main
from vedit.ingest import media
from vedit.project import Project
from vedit.run import ffprobe_json

CLIP = Path(__file__).parent / "fixtures" / "clip-ar-10s.mp4"


@pytest.fixture(autouse=True)
def cfg(tmp_path, monkeypatch):
    d = tmp_path / "cfg"
    d.mkdir()
    monkeypatch.setenv("VEDIT_CONFIG_DIR", str(d))
    return d


def new(*args):
    return main(["new", *map(str, args)])


def make_rec(root: Path, mirror=False, tracks=1) -> Path:
    """A recorder project the test importer (conftest FAKE_IMPORTER) reads."""
    c = root / "Rec X.myrec"
    c.mkdir(parents=True)
    cams = []
    for k in range(tracks):
        shutil.copy(CLIP, c / f"camera-{k}.mp4")
        cams.append(f"camera-{k}.mp4")
    shutil.copy(CLIP, c / "edit.mp4")
    trims = [[k, 0.0, 2.0] for k in range(tracks)]
    d = {"name": "Rec X", "video": "edit.mp4", "camera": cams, "trims": trims, "fps": 25, "mirror": mirror}
    (c / "rec.json").write_text(json.dumps(d))
    return c


def no_ffmpeg(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("ffmpeg ran on a rerun")

    for n in ("run", "proxy_1080p30", "wav48k"):
        monkeypatch.setattr(media, n, boom)


def test_plain_file_project_and_rerun(tmp_path, monkeypatch, capsys):
    f = tmp_path / "My Talk.mp4"
    shutil.copy(CLIP, f)
    assert new(f, "--dir", tmp_path / "out", "--lang", "ar", "--dialect", "iq", "--hint", "Power") == 0
    out = capsys.readouterr().out
    assert "next: cd " in out and "vedit transcribe" in out
    root = tmp_path / "out" / "my-talk"
    p = Project.load(root)
    assert p.slug == "my-talk" and p.lang == "ar" and p.dialect == "iq" and p.hint == "Power"
    assert p.sources["A"].file == f.resolve() and (root / "src/A.mp4").is_symlink()
    for t in ("cuts.yaml", "cues.yaml"):
        data = yaml.safe_load((root / t).read_text())
        assert all(v == [] for v in data.values())
    assert (root / "custom").is_dir()
    m = root / ".vedit/media"
    for rel in ("proxy/A.mp4", "A-48k.wav", "sheet/A.jpg"):
        assert (m / rel).stat().st_size > 0
    assert not (m / "A-cam.mp4").exists()
    v = next(s for s in ffprobe_json(m / "proxy/A.mp4")["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"], v["r_frame_rate"]) == (1920, 1080, "30/1")
    a = ffprobe_json(m / "A-48k.wav")["streams"][0]
    assert (a["sample_rate"], a["channels"]) == ("48000", 2)
    stamps = {x: (m / x).stat().st_mtime_ns for x in ("proxy/A.mp4", "A-48k.wav", "sheet/A.jpg")}
    assert (root / ".vedit/logs/new.log").is_file()
    assert main(["status", "--project", str(root)]) == 0
    assert "ingest      done" in capsys.readouterr().out

    no_ffmpeg(monkeypatch)
    assert new(f, "--dir", tmp_path / "out", "--lang", "ar") == 0  # rerun: nothing redone
    assert stamps == {x: (m / x).stat().st_mtime_ns for x in stamps}
    assert not any(c.name.startswith(".tmp-") for c in m.rglob("*"))


def test_rerun_redoes_only_missing_and_keeps_project_yaml(tmp_path, capsys):
    f = tmp_path / "a.mp4"
    shutil.copy(CLIP, f)
    assert new(f, "--dir", tmp_path, "--lang", "en", "--json") == 0
    root = tmp_path / "a"
    (root / ".vedit/media/sheet/A.jpg").unlink()
    capsys.readouterr()
    assert new(f, "--dir", tmp_path, "--lang", "ar", "--json") == 0
    d = json.loads(capsys.readouterr().out)
    assert d["data"]["built"] == ["sheet/A.jpg"]
    assert any("keeps lang" in i["text"] for i in d["items"])
    assert Project.load(root).lang == "en"


def test_copied_camera_project_keeps_its_media(tmp_path, fake_importer, monkeypatch):
    rec = make_rec(tmp_path)
    assert new(rec, "--dir", tmp_path / "out", "--slug", "t", "--lang", "ar") == 0
    shutil.copytree(tmp_path / "out" / "t", tmp_path / "copy" / "t", symlinks=True)
    m = tmp_path / "copy" / "t" / ".vedit/media"
    stamps = {x: (m / x).stat().st_mtime_ns for x in ("A-cam.mp4", "proxy/A.mp4", "A-48k.wav")}
    no_ffmpeg(monkeypatch)
    assert new(rec, "--dir", tmp_path / "copy", "--slug", "t", "--lang", "ar") == 0  # nothing rebuilt
    assert stamps == {x: (m / x).stat().st_mtime_ns for x in stamps}


def test_old_proxy_hash_is_upgraded_in_place(tmp_path, monkeypatch):
    f = tmp_path / "talk.mp4"
    shutil.copy(CLIP, f)
    assert new(f, "--dir", tmp_path / "out", "--lang", "ar") == 0
    m = tmp_path / "out" / "talk" / ".vedit/media"
    man = json.loads((m / "manifest.json").read_text())
    real = f.resolve()
    src = media.hash_of([str(real), real.stat().st_size])
    man["proxy/A.mp4"] = media.hash_of(
        media.PARAMS["proxy"], src, str(real), real.stat().st_size
    )  # old formula
    (m / "manifest.json").write_text(json.dumps(man))
    no_ffmpeg(monkeypatch)
    assert new(f, "--dir", tmp_path / "out", "--lang", "ar") == 0
    upgraded = json.loads((m / "manifest.json").read_text())["proxy/A.mp4"]
    assert upgraded == media.hash_of(media.PARAMS["proxy"], src, "source", real.stat().st_size)


def test_importer_folder_builds_clean_camera(tmp_path, fake_importer, capsys):
    rec = make_rec(tmp_path, mirror=True)
    assert new(rec, "--dir", tmp_path / "out", "--slug", "t", "--lang", "ar") == 0
    root = tmp_path / "out" / "t"
    p = Project.load(root)
    s = p.sources["A"]
    assert s.importer == "myrec" and s.origin == rec.resolve() and s.mirror and s.fps == 25
    assert [(t.track, t.start, t.end) for t in s.trims] == [(0, 0.0, 2.0)]
    assert (root / "src/A.mp4").resolve() == (rec / "edit.mp4").resolve()
    assert (root / "src/A-camera.mp4").resolve() == s.camera[0] and s.camera[0].name == "camera-0.mp4"
    m = root / ".vedit/media"
    assert "hflip" in (m / "A-cam.filter").read_text()
    streams = ffprobe_json(m / "A-cam.mp4")["streams"]
    assert {s["codec_type"] for s in streams} == {"video", "audio"}
    assert next(s for s in streams if s["codec_type"] == "video")["r_frame_rate"] == "25/1"
    assert (m / "proxy/A.mp4").is_file() and (m / "A-48k.wav").is_file() and (m / "sheet/A.jpg").is_file()
    assert "clean camera on 1 trims" in capsys.readouterr().out


def test_two_camera_tracks_link_and_filter(tmp_path, fake_importer):
    rec = make_rec(tmp_path, tracks=2)
    assert new(rec, "--dir", tmp_path / "out", "--slug", "t", "--lang", "ar") == 0
    root = tmp_path / "out" / "t"
    p = Project.load(root)
    assert [c.name for c in p.sources["A"].camera] == ["camera-0.mp4", "camera-1.mp4"]
    assert (root / "src/A-camera-1.mp4").resolve().name == "camera-1.mp4"
    assert "[1:v]trim" in (root / ".vedit/media/A-cam.filter").read_text()


def test_hand_written_camera_source(tmp_path):
    """No importer: a project.yaml with file + camera (no trims) uses the camera whole with the file's audio."""
    root = tmp_path / "out" / "t"
    (root / "src").mkdir(parents=True)
    shutil.copy(CLIP, root / "src/A.mp4")
    shutil.copy(CLIP, root / "src/A-camera.mp4")
    (root / "project.yaml").write_text(
        "slug: t\nlang: ar\nsources:\n  A: {file: src/A.mp4, camera: src/A-camera.mp4}\n"
    )
    p = Project.load(root)
    plan = media.plan_of(p.sources["A"])
    assert (
        plan.camera.fps == media._fps(CLIP) and len(plan.camera.trims) == 1 and plan.camera.trims[0].end > 9
    )
    assert p.sources["A"].punch_in


def test_folder_without_importer_is_refused(tmp_path, capsys):
    d = tmp_path / "Some.rec"
    d.mkdir()
    assert new(d, "--dir", tmp_path / "out", "--lang", "ar") != 0
    assert "no importer recognises" in capsys.readouterr().err


def test_projects_folder_from_config(tmp_path, cfg, monkeypatch):
    (cfg / "config.yaml").write_text(f"projects: {tmp_path / 'mine'}\n")
    f = tmp_path / "x.mp4"
    shutil.copy(CLIP, f)
    monkeypatch.chdir(tmp_path)
    assert new(f, "--lang", "ar") == 0
    assert (tmp_path / "mine" / "x" / "project.yaml").is_file()


def test_channel_defaults(tmp_path, cfg, capsys):
    (cfg / "config.yaml").write_text("channel: ali\nstyle: global-style\n")
    ch = cfg / "channels" / "ali"
    ch.mkdir(parents=True)
    (ch / "channel.yaml").write_text(
        "style: yellow-doodle\nlang: ar\ndialect: iq\nhint: Names\naccent: '#FFD60A'\n"
    )
    f = tmp_path / "x.mp4"
    shutil.copy(CLIP, f)
    assert new(f, "--dir", tmp_path / "o") == 0
    out = capsys.readouterr().out
    assert "style yellow-doodle (from channel ali)" in out
    p = Project.load(tmp_path / "o" / "x")
    assert (p.lang, p.dialect, p.hint, p.channel) == ("ar", "iq", "Names", "ali")
    assert p.style is None and p.accent is None  # resolved at runtime, not frozen
    assert chan.effective_style(p) == ("yellow-doodle", "channel ali")
    assert chan.effective_accent(p) == ("#FFD60A", "channel ali")
    p.style = "mine"
    assert chan.effective_style(p) == ("mine", "project.yaml")


def test_lang_required(tmp_path, capsys):
    f = tmp_path / "x.mp4"
    shutil.copy(CLIP, f)
    assert new(f, "--dir", tmp_path / "o") == 1
    err = capsys.readouterr().err
    assert "--lang" in err and "next:" in err


def test_unknown_channel_warns(tmp_path, capsys):
    f = tmp_path / "x.mp4"
    shutil.copy(CLIP, f)
    assert new(f, "--dir", tmp_path / "o", "--lang", "en", "--channel", "nope") == 0
    assert "channel 'nope' has no channel.yaml" in capsys.readouterr().out
    assert Project.load(tmp_path / "o" / "x").channel == "nope"


def test_refuses_git_repo(tmp_path, capsys):
    (tmp_path / "repo" / ".git").mkdir(parents=True)
    f = tmp_path / "x.mp4"
    shutil.copy(CLIP, f)
    assert new(f, "--dir", tmp_path / "repo", "--lang", "en") == 1
    err = capsys.readouterr().err
    assert "git work tree" in err and "next:" in err
    assert not (tmp_path / "repo" / "x").exists()
