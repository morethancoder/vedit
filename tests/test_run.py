from pathlib import Path

import pytest

from vedit.run import RunError, ffprobe_duration, frame_grab, hash_of, log_path, run, wav48k

CLIP = Path(__file__).parent / "fixtures" / "clip-ar-10s.mp4"


def test_success_and_log(tmp_path):
    log = log_path(tmp_path, "x")
    p = run(["echo", "hi"], 10, log=log)
    assert p.stdout.strip() == "hi"
    assert "$ echo hi" in log.read_text()


def test_failure_has_tail():
    with pytest.raises(RunError) as e:
        run(["sh", "-c", "for i in $(seq 30); do echo err$i >&2; done; exit 3"], 10)
    msg = str(e.value)
    assert "sh failed" in msg and "exit 3" in msg and "err30" in msg and "err5\n" not in msg


def test_timeout_is_124():
    with pytest.raises(RunError) as e:
        run(["sleep", "5"], 1)
    assert "124" in str(e.value) and "timed out" in str(e.value)


def test_stdin_closed():
    assert run(["cat"], 5).stdout == ""


def test_hash_of(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"abc")
    assert hash_of("a", {"x": 1, "y": 2}) == hash_of("a", {"y": 2, "x": 1})
    assert hash_of(f) == hash_of("abc") != hash_of("abd")
    assert len(hash_of([1, 2])) == 16 and hash_of(b"x") != hash_of(b"y")


def test_media_presets(tmp_path):
    assert 9 < ffprobe_duration(CLIP) < 11
    assert frame_grab(CLIP, 1, tmp_path / "f.jpg").stat().st_size > 0
    w = wav48k(CLIP, tmp_path / "a.wav", start=1, dur=2)
    assert 1.9 < ffprobe_duration(w) < 2.1
