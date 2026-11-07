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


def make_cap(root: Path, mirror=False) -> Path:
    c = root / "Cap X.cap"
    (c / "output").mkdir(parents=True)
    (c / "content/segments/segment-0").mkdir(parents=True)
    shutil.copy(CLIP, c / "content/segments/segment-0/camera.mp4")
    shutil.copy(CLIP, c / "output/result.mp4")
    rec = {"camera": {"path": "content/segments/segment-0/camera.mp4", "fps": 25}}
    (c / "recording-meta.json").write_text(json.dumps({"pretty_name": "Cap X", "segments": [rec]}))
    seg = {"recordingSegment": 0, "start": 0.0, "end": 2.0}
    cfg = {"timeline": {"segments": [seg]}, "camera": {"mirror": mirror}}
    (c / "project-config.json").write_text(json.dumps(cfg))
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


def test_cap_folder_builds_cam(tmp_path, capsys):
    cap = make_cap(tmp_path, mirror=True)
    assert new(cap, "--dir", tmp_path / "out", "--slug", "t", "--lang", "ar") == 0
    root = tmp_path / "out" / "t"
    p = Project.load(root)
    assert p.sources["A"].cap == cap.resolve() and p.sources["A"].camera == "raw"
    assert (root / "src/A.mp4").resolve() == (cap / "output/result.mp4").resolve()
    assert (root / "src/A-camera.mp4").resolve().name == "camera.mp4"
    m = root / ".vedit/media"
    assert "hflip" in (m / "A-cam.filter").read_text()
    streams = ffprobe_json(m / "A-cam.mp4")["streams"]
    assert {s["codec_type"] for s in streams} == {"video", "audio"}
    assert next(s for s in streams if s["codec_type"] == "video")["r_frame_rate"] == "25/1"
    assert (m / "proxy/A.mp4").is_file() and (m / "A-48k.wav").is_file() and (m / "sheet/A.jpg").is_file()


def test_export_file_maps_to_cap(tmp_path, monkeypatch):
    (tmp_path / "caps_dir").mkdir()
    cap = make_cap(tmp_path / "caps_dir")
    monkeypatch.setattr("vedit.ingest.cap.CAP_RECORDINGS", cap.parent)
    export = tmp_path / "Cap X.mp4"
    shutil.copy(CLIP, export)
    assert new(export, "--dir", tmp_path / "out", "--lang", "ar") == 0
    p = Project.load(tmp_path / "out" / "cap-x")
    assert p.sources["A"].cap == cap.resolve()


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
