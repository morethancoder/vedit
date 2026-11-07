"""What an importer plugin hands vedit: an edited video, and optionally the clean camera behind it.

vedit takes any video file. Some recorders also keep the camera on its own, without overlays, zooms or
backgrounds, and store the edit as a list of trims. An importer reads such a project and returns a `Recording`;
`vedit new` then lays the clean camera on those trims with the edited video's audio (`<name>-cam.mp4`) and
treats it like any other source. See `vedit guide importers`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from vedit.report import VeditError


class RecordingError(VeditError):
    """The path belongs to an importer, but the project behind it is missing, broken or unsupported."""


@dataclass
class Trim:
    """One kept stretch of a camera track: `track` is the camera file's index, times in seconds."""

    track: int
    start: float
    end: float


@dataclass
class Camera:
    """Clean camera files (one per track, index 0..n-1) and the trims that, laid end to end, give the edit."""

    tracks: list[Path]
    trims: list[Trim]
    fps: int
    mirror: bool = False

    def check(self, where: str = "camera") -> None:
        if not self.tracks:
            raise RecordingError(f"{where}: no camera file")
        if not self.trims:
            raise RecordingError(f"{where}: no trims")
        bad = [t.track for t in self.trims if not 0 <= t.track < len(self.tracks)]
        if bad:
            raise RecordingError(
                f"{where}: a trim uses track {bad[0]}, but there are {len(self.tracks)} file(s)"
            )
        if any(t.end <= t.start for t in self.trims):
            raise RecordingError(f"{where}: a trim ends before it starts")
        if self.fps <= 0:
            raise RecordingError(f"{where}: fps must be a positive whole number")


@dataclass
class Recording:
    """What `read()` returns. `video` is required: it gives the audio and the timing every stage uses."""

    video: Path
    name: str  # project folder name base
    camera: Camera | None = None
    origin: Path | None = None  # the recorder's own project folder (shown to `vedit clean --posted`)
    extra: dict = field(default_factory=dict)  # anything the importer wants to keep in project.yaml

    @property
    def duration(self) -> float | None:
        return sum(t.end - t.start for t in self.camera.trims) if self.camera else None


def trims_filter(trims: list[Trim], fps: int) -> str:
    """ffmpeg filter_complex script that lays the camera tracks on the trims, end to end.

    Frame counts come from the cumulative edit clock, so rounding never drifts. Input `[k:v]` is track k: pass one
    `-i` per camera file, in track order.
    """
    parts, clock = [], 0.0
    for k, t in enumerate(trims):
        n0 = round(t.start * fps)
        clock1 = clock + t.end - t.start
        n = round(clock1 * fps) - round(clock * fps)
        clock = clock1
        parts.append(f"[{t.track}:v]trim=start_frame={n0}:end_frame={n0 + n},setpts=PTS-STARTPTS[v{k}]")
    n = len(trims)
    return ";".join(parts) + ";" + "".join(f"[v{k}]" for k in range(n)) + f"concat=n={n}:v=1:a=0[v]"
