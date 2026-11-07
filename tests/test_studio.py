import json
import os
import stat
import time
from pathlib import Path

import pytest

from vedit import studio
from vedit.report import VeditError

FIXTURE = Path(__file__).parent / "fixtures" / "clip-ar-10s.wav"

TRANSCRIPT = {
    "segments": [
        {"words": [{"start": 0.1, "end": 0.4, "text": "هلا"}, {"start": 0.5, "end": 0.9, "text": "بيك"}]}
    ]
}

FAKE = """#!/usr/bin/env python3
import json, os, sys
a = sys.argv[1:]
open(os.environ["FAKE_LOG"], "a").write(json.dumps(a) + "\\n")
mode = os.environ.get("FAKE_MODE", "ok")
if mode == "nomodel":
    print(json.dumps({"error": "model qwen3-asr-1.7b is not downloaded", "exit": 1}), file=sys.stderr)
    sys.exit(1)
if mode == "down":
    print("studio: connection refused", file=sys.stderr)
    sys.exit(1)
if "transcribe" in a:
    out = a[a.index("-o") + 1]
    body = json.loads(os.environ["FAKE_BODY"])
    open(out, "w").write(json.dumps(body))
    print("studio: started Studio for this command (it stops by itself)", file=sys.stderr)
    print("queue position 1", file=sys.stderr)
    print("some segments had no word times, so those caption timings are estimated", file=sys.stderr)
    print(json.dumps({"id": "x", "model": "qwen3-asr-1.7b", "warnings": []}))
elif "status" in a:
    print(json.dumps({"reachable": True, "models": {"installed": [], "missing": []}}))
elif a[:1] == ["cutout"] and "--help" in a:
    print("Usage: studio cutout IMAGE|VIDEO" + ("" if mode == "old" else " --start S --duration S"))
elif "cutout" in a:
    out = a[a.index("--out") + 1]
    open(out, "w").write("webm")
    v = {"frames": 151, "fps": 30, "subject": "largest-person", "model": a[a.index("--model") + 1]}
    print(json.dumps({"jobs": [{"id": "j1", "status": "done", "video": v}]}))
elif "models" in a:
    print(json.dumps({"models": [{"id": "qwen3-asr-1.7b", "downloaded": True, "loadable": True}]}))
"""


@pytest.fixture
def fake(tmp_path, monkeypatch):
    bin_ = tmp_path / "bin"
    bin_.mkdir()
    exe = bin_ / "studio"
    exe.write_text(FAKE)
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "calls.log"
    monkeypatch.setenv("PATH", f"{bin_}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_LOG", str(log))
    monkeypatch.setenv("FAKE_BODY", json.dumps({"transcript": TRANSCRIPT}))
    monkeypatch.delenv("FAKE_MODE", raising=False)
    return log


def calls(log):
    return [json.loads(ln) for ln in log.read_text().splitlines()] if log.exists() else []


def test_args_and_warnings(fake, tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"x")
    t = studio.transcribe(wav, "ar", "iq", "Karrada", cache_dir=tmp_path / "c")
    a = calls(fake)[0]
    assert a[:2] == ["--json", "transcribe"]
    for pair in (
        ["--lang", "ar"],
        ["--dialect", "iq"],
        ["--hint", "Karrada"],
        ["--fillers", "keep"],
        ["--model", "qwen3-asr-1.7b"],
    ):
        assert a[a.index(pair[0]) + 1] == pair[1]
    assert "--no-vad" in a and "-o" in a
    assert [w.text for w in t.words] == ["هلا", "بيك"]
    assert t.model == "qwen3-asr-1.7b" and not t.cached
    assert t.warnings == ["some segments had no word times, so those caption timings are estimated"]


def test_cache_hit_skips_call(fake, tmp_path):
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"x")
    studio.transcribe(wav, "ar", cache_dir=tmp_path / "c")
    t = studio.transcribe(wav, "ar", cache_dir=tmp_path / "c")
    assert len(calls(fake)) == 1 and t.cached and len(t.words) == 2 and t.warnings
    studio.transcribe(wav, "ar", fillers="strip", cache_dir=tmp_path / "c")  # option change: new key
    assert len(calls(fake)) == 2


def test_bare_shape_and_vad(fake, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_BODY", json.dumps(TRANSCRIPT))
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"y")
    t = studio.transcribe(wav, "en", vad=True, cache_dir=tmp_path / "c")
    assert len(t.words) == 2 and t.words[0].start == 0.1
    a = calls(fake)[0]
    assert "--no-vad" not in a and "--model" not in a


def test_missing_studio(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    with pytest.raises(VeditError) as e:
        studio.status()
    assert "not on PATH" in e.value.message and "Studio" in e.value.next


def test_model_missing(fake, tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "nomodel")
    wav = tmp_path / "a.wav"
    wav.write_bytes(b"x")
    with pytest.raises(VeditError) as e:
        studio.transcribe(wav, "ar", cache_dir=tmp_path / "c")
    assert "model" in e.value.message and "download" in e.value.next


def test_unreachable_retries_once(fake, monkeypatch):
    monkeypatch.setenv("FAKE_MODE", "down")
    with pytest.raises(VeditError) as e:
        studio.status()
    assert "unreachable" in e.value.message and e.value.next
    assert len(calls(fake)) == 2


def test_status_and_judge_args(fake):
    assert studio.status()["reachable"] is True
    assert calls(fake)[0] == ["--json", "status"]


def test_video_cutout(fake, tmp_path, monkeypatch):
    studio._VIDEO_CUTOUT.clear()
    assert studio.video_cutout_supported()
    out = tmp_path / "m" / "o.webm"
    v = studio.cutout_video(Path("p.mp4"), 11.8934, 5.02, out)
    assert out.exists() and v["frames"] == 151 and v["model"] == "birefnet-lite" and v["job"] == "j1"
    a = calls(fake)[-1]
    assert a[:3] == ["--json", "cutout", "p.mp4"] and a[a.index("--start") + 1] == "11.893"
    assert a[a.index("--duration") + 1] == "5.020" and a[a.index("--out") + 1] == str(out)
    studio._VIDEO_CUTOUT.clear()
    monkeypatch.setenv("FAKE_MODE", "old")
    assert not studio.video_cutout_supported()
    studio._VIDEO_CUTOUT.clear()


def test_speech_models(fake):
    assert studio.speech_models()[0]["id"] == "qwen3-asr-1.7b"
    assert calls(fake)[0] == ["--json", "models", "--speech"]


@pytest.mark.studio
@pytest.mark.skipif(os.environ.get("VEDIT_STUDIO_TESTS") != "1", reason="set VEDIT_STUDIO_TESTS=1")
def test_real_transcribe(tmp_path):
    t0 = time.time()
    t = studio.transcribe(FIXTURE, "ar", "iq", cache_dir=tmp_path)
    print(f"\nwords={len(t.words)} secs={time.time() - t0:.1f} model={t.model} warnings={t.warnings}")
    assert t.words and all(w.end >= w.start >= 0 for w in t.words)
