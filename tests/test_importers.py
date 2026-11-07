"""Importer plugins load from the config folder; user logos come from config, channel and project."""

import json

import pytest

from vedit import importers
from vedit.cli import main
from vedit.graphics.cues import custom_logos
from vedit.project import Paths
from vedit.recording import Camera, RecordingError, Trim, trims_filter
from vedit.report import VeditError


def test_no_plugins_means_plain_video(tmp_path):
    assert importers.load() == [] and importers.recognise(tmp_path) is None


def test_loads_skips_private_and_test_files(fake_importer, tmp_path):
    d = fake_importer / "importers"
    (d / "_helper.py").write_text("raise SystemExit('never loaded')")
    (d / "test_myrec.py").write_text("raise SystemExit('never loaded')")
    [imp] = importers.load()
    assert imp.name == "myrec" and imp.about.startswith("Test recorder")
    rec_dir = tmp_path / "r"
    rec_dir.mkdir()
    (rec_dir / "rec.json").write_text(json.dumps(
        {"name": "R", "video": "v.mp4", "camera": ["c.mp4"], "trims": [[0, 0, 1]], "fps": 25}))  # fmt: skip
    got = importers.recognise(rec_dir)
    assert got and got[0].name == "myrec" and got[1].camera.fps == 25
    assert importers.get("myrec").originals(rec_dir) == ([(rec_dir, "myrec project")], [])


def test_extra_dirs_and_broken_plugins(tmp_path, monkeypatch):
    extra = tmp_path / "more"
    extra.mkdir()
    (extra / "x.py").write_text("NAME = 'x'\ndef read(p): return None\n")
    monkeypatch.setenv("VEDIT_IMPORTERS", str(extra))
    assert [i.name for i in importers.load()] == ["x"]
    (extra / "y.py").write_text("def nope(): pass\n")
    with pytest.raises(VeditError, match="no read"):
        importers.load()
    (extra / "y.py").write_text("raise ValueError('boom')\n")
    with pytest.raises(VeditError, match="failed to load: boom"):
        importers.load()


def test_bad_camera_from_a_plugin_is_refused(tmp_path):
    cam = Camera([tmp_path / "c.mp4"], [Trim(1, 0, 1)], 25)
    with pytest.raises(RecordingError, match="track 1"):
        cam.check()


def test_trims_filter_frames_follow_the_edit_clock():
    f = trims_filter([Trim(0, 0.0, 1.0), Trim(1, 2.0, 3.5)], 25)
    assert f == (
        "[0:v]trim=start_frame=0:end_frame=25,setpts=PTS-STARTPTS[v0];"
        "[1:v]trim=start_frame=50:end_frame=87,setpts=PTS-STARTPTS[v1];[v0][v1]concat=n=2:v=1:a=0[v]"
    )


def test_importers_command_lists_and_matches(fake_importer, tmp_path, capsys):
    plain = tmp_path / "x.mp4"
    plain.write_bytes(b"x")
    assert main(["importers", str(plain), "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert [i["name"] for i in d["data"]["importers"]] == ["myrec"] and d["data"]["match"] is None


def test_user_logos_config_then_channel_then_project(tmp_path, monkeypatch):
    cfg = tmp_path / "cfg"
    monkeypatch.setenv("VEDIT_CONFIG_DIR", str(cfg))
    for d, names in ((cfg / "logos", ["mine", "both"]), (cfg / "channels/ch/logos", ["both", "chan"]),
                     (tmp_path / "p/custom/logos", ["proj"])):  # fmt: skip
        d.mkdir(parents=True)
        for n in names:
            (d / f"{n}.svg").write_text("<svg/>")
    got = custom_logos(Paths(tmp_path / "p"), "ch")
    assert sorted(got) == ["both", "chan", "mine", "proj"] and "channels" in str(got["both"])
    assert "both" in custom_logos(Paths(tmp_path / "p")) and "chan" not in custom_logos(Paths(tmp_path / "p"))
