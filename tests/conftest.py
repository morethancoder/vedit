"""The speech clip fixture (tests/fixtures/clip-ar-10s.*) is a cut of a real talk and is not published.
Without it, a synthetic stand-in of the same shape is generated once: 10 s, 854x480 h264 + mono AAC, and a
48 kHz mono WAV. Tests that need real speech go through Studio and are marked `studio`."""

import shutil
import subprocess
from pathlib import Path

FIX = Path(__file__).parent / "fixtures"
MP4, WAV = FIX / "clip-ar-10s.mp4", FIX / "clip-ar-10s.wav"


def pytest_configure(config):
    if MP4.exists() and WAV.exists():
        return
    if not shutil.which("ffmpeg"):
        return
    FIX.mkdir(exist_ok=True)
    tb = [shutil.which("timeout") or shutil.which("gtimeout")]
    pre = [tb[0], "60"] if tb[0] else []
    common = [*pre, "ffmpeg", "-v", "error", "-y"]
    if not MP4.exists():
        subprocess.run([*common, "-f", "lavfi", "-i", "testsrc2=size=854x480:rate=30:duration=10",
                        "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000:duration=10",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-ac", "1", "-shortest", str(MP4)],
                       check=True, stdin=subprocess.DEVNULL)  # fmt: skip
    if not WAV.exists():
        subprocess.run([*common, "-f", "lavfi", "-i", "sine=frequency=220:sample_rate=48000:duration=10",
                        "-ac", "1", str(WAV)], check=True, stdin=subprocess.DEVNULL)  # fmt: skip


import pytest

FAKE_IMPORTER = '''"""Test recorder: a folder with rec.json naming the edited video, camera and trims."""
import json
from pathlib import Path

from vedit.recording import Camera, Recording, Trim

NAME = "myrec"


def read(path):
    path = Path(path)
    if not (path / "rec.json").is_file():
        return None
    d = json.loads((path / "rec.json").read_text())
    cam = Camera([path / c for c in d["camera"]], [Trim(*t) for t in d["trims"]], d["fps"], d.get("mirror", False))
    return Recording(video=path / d["video"], name=d["name"], camera=cam, origin=path)


def originals(origin):
    return [(Path(origin), "myrec project")], []
'''


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path_factory, monkeypatch):
    """Every test gets an empty config folder: the real ~/.config/vedit (its packs, channels and private
    importer plugins) never leaks into a test run. Tests that need config set VEDIT_CONFIG_DIR themselves."""
    monkeypatch.setenv("VEDIT_CONFIG_DIR", str(tmp_path_factory.mktemp("cfg")))
    monkeypatch.delenv("VEDIT_IMPORTERS", raising=False)


@pytest.fixture
def fake_importer(tmp_path, monkeypatch):
    """Install the test importer in a fresh config folder; returns that folder."""
    d = tmp_path / "cfgimp"
    (d / "importers").mkdir(parents=True)
    (d / "importers" / "myrec.py").write_text(FAKE_IMPORTER)
    monkeypatch.setenv("VEDIT_CONFIG_DIR", str(d))
    return d
