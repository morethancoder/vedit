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
