"""Ingest media: A-cam (clean camera on its trims), proxies, 48 kHz WAV, contact sheets.

Every output is made under a temp name and renamed, and recorded in `.vedit/media/manifest.json` as
output -> input hash (source path + size + params). An output is redone only when missing or its hash changed.
"""

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from vedit.project import Paths
from vedit.recording import Camera, Trim, trims_filter
from vedit.run import DECODE, FF, enc_h264, ffprobe_json, hash_of, proxy_1080p30, run, wav48k

SHEET_COLS, SHEET_ROWS, SHEET_TILE_W = 4, 4, 480
PARAMS = {"cam": "q75-g50-v1", "proxy": "1080p30-8M-v1", "wav": "48k-stereo-v1", "sheet": "4x4-480-v2"}


@dataclass
class SourcePlan:
    name: str
    file: Path  # the edited video: its audio is the source's audio
    camera: Camera | None = None  # clean camera laid on its trims, when the recorder kept one

    @property
    def audio(self) -> Path:
        return self.file


def _fps(path: Path) -> int:
    for st in ffprobe_json(path).get("streams", []):
        if st.get("codec_type") == "video":
            n, _, d = str(st.get("avg_frame_rate") or st.get("r_frame_rate") or "30/1").partition("/")
            return max(1, round(float(n) / float(d or 1))) if float(d or 1) else 30
    return 30


def plan_of(s) -> SourcePlan:
    """A project.yaml source as an ingest plan. Paths are resolved (links followed) so hashes name real files.
    A camera without trims is used whole; a camera without fps uses its own frame rate."""
    f = Path(s.file).resolve()
    if not s.camera:
        return SourcePlan(s.name, f)
    tracks = [Path(c).resolve() for c in s.camera]
    trims = s.trims or [Trim(0, 0.0, float(ffprobe_json(tracks[0])["format"]["duration"]))]
    cam = Camera(tracks, trims, s.fps or _fps(tracks[0]), s.mirror)
    cam.check(f"sources.{s.name}")
    return SourcePlan(s.name, f, cam)


def _size(p: Path) -> int:
    return p.stat().st_size


def has_audio(path: Path) -> bool:
    return any(s.get("codec_type") == "audio" for s in ffprobe_json(path).get("streams", []))


class Manifest:
    def __init__(self, paths: Paths):
        self.path = paths.media / "manifest.json"
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        self.data: dict[str, str] = data if isinstance(data, dict) else {}

    def save(self) -> None:
        tmp = self.path.with_name(".manifest.tmp")
        tmp.write_text(json.dumps(self.data, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, self.path)


def ensure(
    manifest: Manifest,
    out: Path,
    key: str,
    in_hash: str,
    make: Callable[[Path], object],
    legacy: str | None = None,
) -> bool:
    """Build `out` via make(tmp) unless it exists with this input hash. True when it was built.

    `legacy` is the same input under an older hash formula: a match is upgraded in place, not rebuilt."""
    if out.is_file() and legacy and manifest.data.get(key) == legacy:
        manifest.data[key] = in_hash
        manifest.save()
    if out.is_file() and manifest.data.get(key) == in_hash:
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(f".tmp-{out.name}")
    tmp.unlink(missing_ok=True)
    manifest.data.pop(key, None)
    try:
        make(tmp)
        os.replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)
    manifest.data[key] = in_hash
    manifest.save()
    return True


def cam_filter(cam: Camera) -> str:
    f = trims_filter(cam.trims, cam.fps)
    if cam.mirror:
        f = f[: -len("[v]")] + "[vc];[vc]hflip[v]"
    return f


def make_cam(cam: Camera, video: Path, script: Path, dst: Path, log: Path) -> None:
    """Clean camera track(s) -> laid on the trims -> the edited video's audio, copied (port of T source.sh)."""
    script.write_text(cam_filter(cam), encoding="utf-8")
    cmd = [*FF, *DECODE]
    for c in cam.tracks:
        cmd += ["-i", str(c)]
    n = len(cam.tracks)
    cmd += ["-i", str(video), "-filter_complex_script", str(script), "-map", "[v]", "-map", f"{n}:a"]
    cmd += ["-r", str(cam.fps), *enc_h264(quality=75, gop=50)]
    cmd += ["-c:a", "copy", "-movflags", "+faststart", str(dst)]
    run(cmd, 3600, log=log)


def make_sheet(src: Path, dst: Path, duration: float, log: Path) -> None:
    """One contact sheet: 4x4 tiles evenly spaced over the duration, 480 px wide."""
    # one fast seek per tile (decoding the whole proxy took ~2 min for a 15 min talk)
    n = SHEET_COLS * SHEET_ROWS
    step = max(duration, 0.1) / n
    cmd = [*FF]
    for i in range(n):
        cmd += ["-ss", f"{(i + 0.5) * step:.3f}", "-i", str(src)]
    one = [f"[{i}:v]trim=end_frame=1,setpts=PTS-STARTPTS,scale={SHEET_TILE_W}:-2[t{i}]" for i in range(n)]
    tiles = "".join(f"[t{i}]" for i in range(n))
    graph = ";".join(one) + f";{tiles}concat=n={n}:v=1:a=0,tile={SHEET_COLS}x{SHEET_ROWS}[s]"
    cmd += ["-filter_complex", graph, "-map", "[s]", "-frames:v", "1", "-q:v", "3", "-update", "1", str(dst)]
    run(cmd, 600, log=log)


def ingest_media(
    paths: Paths, plans: list[SourcePlan], log: Path, dry: bool = False
) -> tuple[list[Path], list[str], list[str]]:
    """Make every missing output. Returns (outputs, names built this run, warnings).

    dry: build and write nothing; `built` lists what a real run would build."""
    m = paths.media
    man = Manifest(paths)
    outputs: list[Path] = []
    built: list[str] = []
    warns: list[str] = []

    def would_build(out: Path) -> None:
        outputs.append(out)
        built.append(out.relative_to(m).as_posix())

    def step(out: Path, in_hash: str, make, legacy: str | None = None) -> None:
        if dry:
            if out.is_file() and man.data.get(out.relative_to(m).as_posix()) in (in_hash, legacy):
                outputs.append(out)
            else:
                would_build(out)
            return
        outputs.append(out)
        if ensure(man, out, out.relative_to(m).as_posix(), in_hash, make, legacy):
            built.append(out.relative_to(m).as_posix())

    for p in plans:
        cam, f = p.camera, p.file
        if cam is not None:
            cams = [[str(c), _size(c)] for c in cam.tracks]
            segs = [[t.track, t.start, t.end] for t in cam.trims]
            cam_hash = hash_of(PARAMS["cam"], cams, [str(f), _size(f)], segs, cam.fps, cam.mirror)
            vid = m / f"{p.name}-cam.mp4"
            step(
                vid,
                cam_hash,
                lambda t, cam=cam, f=f, p=p: make_cam(cam, f, m / f"{p.name}-cam.filter", t, log),
            )
        else:
            vid, cam_hash = f, None
        src_hash = hash_of([str(f), _size(f)])
        proxy = m / "proxy" / f"{p.name}.mp4"
        sheet = m / "sheet" / f"{p.name}.jpg"
        # dry run: whatever is made after a rebuilt A-cam (proxy, then sheet) is rebuilt too
        chain = dry and (vid.relative_to(m).as_posix() in built if vid.is_relative_to(m) else False)
        if chain or (dry and not vid.is_file()):
            would_build(proxy)
        else:
            # keyed on what the proxy is made from, never on where the project lives (a copied project keeps it)
            step(proxy, hash_of(PARAMS["proxy"], src_hash, cam_hash or "source", _size(vid)),
                 lambda t, vid=vid: proxy_1080p30(vid, t, log=log),
                 legacy=hash_of(PARAMS["proxy"], src_hash, str(vid), _size(vid)))  # fmt: skip
        if has_audio(p.audio):
            step(m / f"{p.name}-48k.wav", hash_of(PARAMS["wav"], src_hash),
                 lambda t, a=p.audio: wav48k(a, t, mono=False, log=log))  # fmt: skip
        else:
            warns.append(f"{p.name}: {p.audio.name} has no audio stream; no WAV made")
        if dry and f"proxy/{p.name}.mp4" in built:
            would_build(sheet)
            continue
        dur = float(ffprobe_json(proxy)["format"]["duration"])
        step(sheet, hash_of(PARAMS["sheet"], _size(proxy), round(dur, 1)),
             lambda t, proxy=proxy, dur=dur: make_sheet(proxy, t, dur, log))  # fmt: skip
    return outputs, built, warns
