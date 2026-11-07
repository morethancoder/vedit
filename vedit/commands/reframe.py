"""vedit reframe: the face-following crop of every non-16:9 output (cached), with a check sheet that draws the
crop on the 16:9 frames. `vedit build` uses the same paths; run this to look before building."""

from __future__ import annotations

import itertools
from pathlib import Path

from vedit import outputs as om
from vedit.formats import reframe as rf
from vedit.graphics import faces
from vedit.project import Project, ProjectError, find_project
from vedit.report import Report, VeditError
from vedit.words.timeline import Edl

EPILOG = "example: vedit reframe reel-1 --sheet"


def add_args(sp) -> None:
    sp.add_argument(
        "outputs", nargs="*", metavar="OUTPUT", help="output ids (default: every non-16:9 output)"
    )
    sp.add_argument(
        "--sheet", action="store_true", help="draw the crop over 16 frames: .vedit/reframe/<id>.jpg"
    )
    sp.epilog = EPILOG


def span(project: Project, edl: Edl, out, wbc=None) -> tuple[float, float]:
    """Program-time span of an output: a clip's word range mapped through the cut, else the whole program."""
    if not out.range:
        return 0.0, edl.total
    rng = om.resolve_range(project, out, wbc)
    return edl.g(rng.clip, rng.t0), edl.g(rng.clip, rng.t1)


def crop_path(project: Project, out, edl: Edl | None = None, track=None, wbc=None) -> tuple[list[dict], dict]:
    """(points, info) for one output, from the cache when the face track, cut, span and aspect are unchanged."""
    paths = project.paths
    edl = edl or Edl.load(paths.edl / "edl.json")
    t0, t1 = span(project, edl, out, wbc)
    track = track or faces.FaceTrack.load(paths, list(project.sources), edl)
    fkey = "|".join(faces.load_clip(paths, c)[2] for c in project.sources)
    k = rf.key(fkey, {"pieces": edl.pieces, "total": edl.total}, t0, t1, out.aspect)
    cache = paths.vedit / "reframe" / f"{out.id}.json"
    pts = rf.cached(cache, k)
    hit = pts is not None
    if pts is None:
        pts = rf.path(track, edl, t0, t1, out.aspect)
        rf.save(cache, k, pts, out.aspect)
    moves = sum(1 for a, b in itertools.pairwise(pts) if abs(a["x"] - b["x"]) > 0.5 and not b.get("cut"))
    info = {"id": out.id, "aspect": out.aspect, "t0": round(t0, 3), "t1": round(t1, 3),
            "crop_w": rf.crop_width(out.aspect), "points": len(pts), "moving_steps": moves,
            "cached": hit, "file": str(cache)}  # fmt: skip
    return pts, info


def sheet(project: Project, out, pts: list[dict], track, edl: Edl) -> Path:
    """4x4 frames over the span with the crop (green) and the face (white) drawn on the 16:9 frame."""
    import cv2
    import numpy as np

    from vedit.run import frame_grab

    paths = project.paths
    t0, t1 = pts[0]["t"], pts[-1]["t"]
    cw = rf.crop_width(out.aspect)
    tmp = paths.vedit / "reframe" / f"{out.id}-frames"
    tmp.mkdir(parents=True, exist_ok=True)
    tiles = []
    for k in range(16):
        t = t0 + (t1 - t0) * (k + 0.5) / 16
        clip, st = edl.src(t)
        img = cv2.imread(str(frame_grab(faces.proxy_of(paths, clip), st, tmp / f"{k:02d}.jpg", timeout=120)))
        img = np.zeros((1080, 1920, 3), np.uint8) if img is None else cv2.resize(img, (1920, 1080))
        x = int(rf.x_at(pts, t))
        shade = img.copy()
        shade[:, :x] //= 3
        shade[:, x + int(cw) :] //= 3
        row = track.at(t)
        if row["box"]:
            b = row["box"]
            cv2.rectangle(shade, (b[0], b[1]), (b[0] + b[2], b[1] + b[3]), (255, 255, 255), 4)
        cv2.rectangle(shade, (x, 0), (x + int(cw), 1079), (0, 220, 0), 10)
        cv2.putText(shade, f"{t:.1f}s", (30, 90), cv2.FONT_HERSHEY_SIMPLEX, 3, (255, 255, 255), 8)
        tiles.append(cv2.resize(shade, (480, 270)))
    grid = np.vstack([np.hstack(tiles[r * 4 : (r + 1) * 4]) for r in range(4)])
    dst = paths.vedit / "reframe" / f"{out.id}.jpg"
    cv2.imwrite(str(dst), grid, [cv2.IMWRITE_JPEG_QUALITY, 85])
    for f in tmp.iterdir():
        f.unlink()
    tmp.rmdir()
    return dst


def run(ns) -> Report:
    try:
        project = Project.load(find_project(override=ns.project))
    except ProjectError as e:
        raise VeditError(str(e), next="vedit new <recording>", code="bad_input") from e
    paths = project.paths
    if not (paths.edl / "edl.json").is_file():
        raise VeditError(f"{paths.edl / 'edl.json'} is not built yet", next="vedit cut", code="not_built")
    known = {o.id: o for o in project.outputs}
    for oid in ns.outputs:
        if oid not in known:
            raise VeditError(f"no output called {oid!r}", next="vedit output list", code="bad_input")
    todo = (
        [known[o] for o in ns.outputs] if ns.outputs else [o for o in project.outputs if o.aspect != "16:9"]
    )
    r = Report("reframe")
    if not todo:
        r.info("every output is 16:9: nothing to reframe")
        r.next = "vedit output add <id> --kind clip ...  (vedit guide formats)"
        return r
    edl = Edl.load(paths.edl / "edl.json")
    track = faces.FaceTrack.load(paths, list(project.sources), edl)
    wbc = om.words_by_clip(project) if any(o.range for o in todo) else None
    rows = []
    for o in todo:
        pts, info = crop_path(project, o, edl, track, wbc)
        r.ok_(f"{o.id}: {o.aspect} crop {info['crop_w']:.0f} px wide over {info['t0']:.1f}-{info['t1']:.1f}s, "
              f"moves on {info['moving_steps']} of {info['points']} steps" + (" (cached)" if info["cached"] else ""))  # fmt: skip
        r.artifact(info["file"], "crop-path")
        if ns.sheet:
            img = sheet(project, o, pts, track, edl)
            info["sheet"] = str(img)
            r.artifact(img, "image")
            r.info(f"sheet: {img}")
        rows.append(info)
    r.data = {"outputs": rows}
    r.next = "vedit build"
    return r
