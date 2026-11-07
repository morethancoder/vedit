import json

from vedit import studio
from vedit.cli import main
from vedit.commands import doctor
from vedit.report import VeditError


def patch_all(monkeypatch, level="ok"):
    for n in ("ffmpeg", "ffprobe", "node", "hyperframes", "ollama"):
        monkeypatch.setattr(doctor, f"check_{n}", lambda: (level, "x"))
    monkeypatch.setattr(doctor, "check_studio", lambda: [("ok", "studio")])
    monkeypatch.setattr(doctor, "check_disk", lambda root, stage: ("ok", f"disk {stage}"))


def test_all_ok(monkeypatch, tmp_path, capsys):
    patch_all(monkeypatch)
    monkeypatch.chdir(tmp_path)
    assert main(["doctor", "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["ok"] and d["data"]["next_stage"] == "render" and d["data"]["project"] is None


def test_fail_exits_1_warn_does_not(monkeypatch, tmp_path):
    patch_all(monkeypatch, "warn")
    monkeypatch.chdir(tmp_path)
    assert main(["doctor"]) == 0
    patch_all(monkeypatch, "fail")
    assert main(["doctor"]) == 1


def test_studio_down_and_asr_unknown(monkeypatch):
    def boom(**k):
        raise VeditError("not running")

    monkeypatch.setattr(studio, "status", boom)
    res = doctor.check_studio()
    assert res[0][0] == "fail" and res[1][0] == "warn"
    monkeypatch.setattr(studio, "status", lambda **k: {"reachable": True, "models": {"installed": ["z"]}})
    monkeypatch.setattr(studio, "video_cutout_supported", lambda: True)
    monkeypatch.setattr(studio, "speech_models", boom)
    res = doctor.check_studio()
    assert res[0][0] == "ok" and res[1][0] == "warn" and "unknown" in res[1][1] and res[2][0] == "ok"
    ready = {"id": "qwen3-asr-1.7b", "downloaded": True, "loadable": True}
    monkeypatch.setattr(studio, "speech_models", lambda **k: [ready])
    assert doctor.check_studio()[1][0] == "ok"
    monkeypatch.setattr(studio, "speech_models", lambda **k: [{**ready, "downloaded": False}])
    assert doctor.check_studio()[1][0] == "fail"
    monkeypatch.setattr(studio, "speech_models", lambda **k: [])
    assert doctor.check_studio()[1][0] == "fail"
    monkeypatch.setattr(studio, "video_cutout_supported", lambda: False)
    res = doctor.check_studio()
    assert res[2][0] == "warn" and "remove-background" in res[2][1]


def test_disk(tmp_path, monkeypatch):
    assert doctor.check_disk(tmp_path, "ingest")[0] in ("ok", "warn")
    monkeypatch.setitem(doctor.DISK_GB, "render", 10**9)
    assert doctor.check_disk(tmp_path, "render")[0] == "fail"
