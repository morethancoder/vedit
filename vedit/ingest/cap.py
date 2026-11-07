"""Read a Cap `.cap` project: raw camera, timeline segments, export; match exports to their `.cap`."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from vedit.report import VeditError
from vedit.run import ffprobe_duration

CAP_RECORDINGS = Path.home() / "Library" / "Application Support" / "so.cap.desktop" / "recordings"
DEFAULT_SEARCH = (CAP_RECORDINGS, str(Path.home() / "Movies" / "YT" / "*"))
EXPORT_EXTS = (".mp4", ".mov")


class CapError(VeditError):
    """A Cap project is missing, unreadable or unsupported."""


@dataclass
class Segment:
    recording_segment: int
    start: float
    end: float


@dataclass
class CapProject:
    path: Path
    camera: Path
    display: Path | None
    export: Path | None
    segments: list[Segment]
    camera_fps: int
    pretty_name: str
    mirror: bool = False
    cameras: dict[int, Path] = field(default_factory=dict)  # recording segment -> camera file

    @property
    def duration(self) -> float:
        return sum(s.end - s.start for s in self.segments)


def _load(path: Path) -> dict:
    if not path.is_file():
        raise CapError(f"{path} is missing: not a complete Cap project")
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        raise CapError(f"{path} is not valid JSON: {e}") from e
    if not isinstance(data, dict):
        raise CapError(f"{path} should hold a JSON object")
    return data


def _cap_root(path: Path) -> Path:
    p = Path(path).expanduser().resolve()
    for cand in (p, *p.parents):
        if cand.suffix == ".cap" and cand.is_dir():
            return cand
    raise CapError(f"{path} is not a .cap folder nor inside one")


def read_cap(path: Path, search=DEFAULT_SEARCH) -> CapProject:
    """Read the `.cap` folder at `path` (or any path inside it)."""
    root = _cap_root(path)
    meta_file, cfg_file = root / "recording-meta.json", root / "project-config.json"
    meta, cfg = _load(meta_file), _load(cfg_file)
    rec = meta.get("segments")
    if not isinstance(rec, list) or not rec:
        raise CapError(f"{meta_file}: no recording segments")
    cameras: dict[int, Path] = {}
    for i, r in enumerate(rec):
        cam = (r or {}).get("camera")
        if cam and cam.get("path"):
            cameras[i] = root / cam["path"]
    if not cameras:
        raise CapError(f"{meta_file}: no camera in the recording (screen-only Cap project)")
    if 0 not in cameras:
        raise CapError(f"{meta_file}: recording segment 0 has no camera")
    missing = [p for p in cameras.values() if not p.is_file()]
    if missing:
        raise CapError(f"{missing[0]} is missing (camera file named in {meta_file.name})")
    segs = []
    for s in (cfg.get("timeline") or {}).get("segments") or []:
        if float(s.get("timescale", 1.0)) != 1.0:
            raise CapError(
                f"{cfg_file}: timeline segment with timescale {s['timescale']} (speed change) is unsupported"
            )
        segs.append(Segment(int(s.get("recordingSegment", 0)), float(s["start"]), float(s["end"])))
    if not segs:
        raise CapError(f"{cfg_file}: timeline has no segments")
    bad = [s.recording_segment for s in segs if s.recording_segment not in cameras]
    if bad:
        raise CapError(f"{cfg_file}: timeline uses recording segment {bad[0]} which has no camera")
    disp = (rec[0].get("display") or {}).get("path")
    result = root / "output" / "result.mp4"
    cap = CapProject(
        path=root,
        camera=cameras[0],
        display=root / disp if disp else None,
        export=result if result.is_file() else None,
        segments=segs,
        camera_fps=round(float(rec[0]["camera"].get("fps") or 25)),
        pretty_name=str(meta.get("pretty_name") or root.stem),
        mirror=bool((cfg.get("camera") or {}).get("mirror", False)),
        cameras=cameras,
    )
    if cap.export is None:
        cap.export = find_export(cap, search)
    return cap


def segment_filter(segments: list[Segment], fps: int) -> str:
    """ffmpeg filter_complex script laying the raw camera on the Cap timeline (port of T source.sh).

    Frame counts come from the cumulative export clock, so rounding never drifts. The input index is the
    recording segment (`[k:v]`): pass one `-i` per camera file, in recording-segment order (a single
    recording gives `[0:v]` throughout).
    """
    parts, clock = [], 0.0
    for k, s in enumerate(segments):
        n0 = round(s.start * fps)
        clock1 = clock + s.end - s.start
        n = round(clock1 * fps) - round(clock * fps)
        clock = clock1
        parts.append(
            f"[{s.recording_segment}:v]trim=start_frame={n0}:end_frame={n0 + n},setpts=PTS-STARTPTS[v{k}]"
        )
    n = len(segments)
    return ";".join(parts) + ";" + "".join(f"[v{k}]" for k in range(n)) + f"concat=n={n}:v=1:a=0[v]"


def _search_dirs(search) -> list[Path]:
    dirs: list[Path] = []
    for s in search:
        s = Path(s).expanduser()
        dirs += sorted(Path(m) for m in _glob(s)) if any(c in str(s) for c in "*?[") else [s]
    return [d for d in dirs if d.is_dir()]


def _glob(pattern: Path):
    import glob

    return glob.glob(str(pattern))


def find_export(cap: CapProject, search=DEFAULT_SEARCH) -> Path | None:
    """`<cap>/output/result.mp4`, else `<pretty_name>.mp4/.mov` in the search dirs (globs allowed)."""
    result = cap.path / "output" / "result.mp4"
    if result.is_file():
        return result
    for d in _search_dirs(search):
        for ext in EXPORT_EXTS:
            if (d / f"{cap.pretty_name}{ext}").is_file():
                return d / f"{cap.pretty_name}{ext}"
    return None


def _timeline_duration(cap_dir: Path) -> float | None:
    try:
        segs = _load(cap_dir / "project-config.json")["timeline"]["segments"]
        return sum(float(s["end"]) - float(s["start"]) for s in segs)
    except (CapError, KeyError, TypeError, ValueError):
        return None


def find_cap_for_export(export: Path, roots=None) -> Path:
    """Match an export file to its `.cap`: pretty_name == stem, then result.mp4 size, then duration."""
    export = Path(export).expanduser()
    if not export.is_file():
        raise CapError(f"{export} does not exist")
    roots = [Path(r).expanduser() for r in (roots or [CAP_RECORDINGS])]
    caps = sorted(c for r in roots if r.is_dir() for c in r.glob("*.cap") if c.is_dir())
    if not caps:
        raise CapError("no .cap projects found in " + ", ".join(str(r) for r in roots))

    def names(c: Path) -> str | None:
        try:
            return _load(c / "recording-meta.json").get("pretty_name")
        except CapError:
            return None

    def pick(found: list[Path], how: str) -> Path | None:
        if len(found) == 1:
            return found[0]
        if len(found) > 1:
            raise CapError(
                f"{export.name} matches several .cap projects by {how}:\n  "
                + "\n  ".join(str(c) for c in found)
            )
        return None

    size = export.stat().st_size
    by_size = [c for c in caps if (c / "output" / "result.mp4").is_file()
               and (c / "output" / "result.mp4").stat().st_size == size]  # fmt: skip
    by_name = [c for c in caps if names(c) == export.stem]
    if len(by_name) > 1 and by_size:
        by_name = [c for c in by_name if c in by_size] or by_name
    for found, how in ((by_name, "pretty_name"), (by_size, "file size")):
        hit = pick(found, how)
        if hit:
            return hit
    dur = ffprobe_duration(export)
    by_dur = [c for c in caps if (d := _timeline_duration(c)) is not None and abs(d - dur) <= 0.1]
    hit = pick(by_dur, "duration")
    if hit:
        return hit
    raise CapError(
        f"no .cap matches {export.name} (by name, size or duration) under " + ", ".join(str(r) for r in roots)
    )
