"""vedit faces: face track for placement (cached); --sheet draws a check sheet."""

from __future__ import annotations

from vedit import state
from vedit.graphics import faces
from vedit.project import Project, ProjectError, find_project
from vedit.report import Report, VeditError
from vedit.run import hash_of
from vedit.words.timeline import Edl

EPILOG = "example: vedit faces --sheet"


def add_args(sp) -> None:
    sp.add_argument("--sheet", action="store_true", help="write .vedit/faces/sheet.jpg (boxes on frames)")
    sp.add_argument("--force", action="store_true", help="ignore the cache and sample again")
    sp.epilog = EPILOG


def run(ns) -> Report:
    try:
        project = Project.load(find_project(override=ns.project))
    except ProjectError as e:
        raise VeditError(str(e), next="vedit new <video>  (or: vedit faces --project PATH)") from e
    paths = project.paths
    clips = list(project.sources)
    r = Report("faces")
    rows, keys, hits = {}, [], []
    for c in clips:
        rows[c], hit, key = faces.load_clip(paths, c, ns.force)
        keys.append(key)
        hits.append(hit)
    track = faces.FaceTrack(rows)
    n = sum(len(v) for v in rows.values())
    cams = sum(x["cam"] for v in rows.values() for x in v)
    withface = sum(1 for v in rows.values() for x in v if x["box"])
    outputs = [paths.faces / f"{c}.json" for c in clips]
    r.ok_(
        f"{n} samples at {faces.FPS}/s, {withface} with a face, {cams} camera-shot "
        f"({100 * cams / max(n, 1):.0f}%); cache {'hit' if all(hits) else 'miss (sampled)'}"
    )
    data = {"samples": n, "with_face": withface, "cam": cams, "cache_hit": all(hits)}
    if ns.sheet:
        edl_f = paths.edl / "edl.json"
        if not edl_f.is_file():
            raise VeditError(f"{edl_f} is not built yet", next="vedit cut")
        track.edl = Edl.load(edl_f)
        out = faces.sheet(track, paths)
        outputs.append(out)
        data["sheet"] = str(out)
        r.info(f"sheet: {out}  (green = camera shot, orange = other face, red = no face)")
    state.record_stage(paths, "faces", hash_of(keys), outputs)
    r.data = data
    r.next = "vedit faces --sheet" if not ns.sheet else "vedit guide cues"
    return r
