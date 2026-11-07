"""vedit review: snapshot every graphic of the build at its peak, contact sheets + measured flags.

How the numbers are got: vedit/review/capture.py (probe in a review copy of the hf project); what is
flagged and why: vedit/review/flags.py. Output under `.vedit/review/`: sheet-NN.jpg, report.json, cache/.
"""

from __future__ import annotations

import json
from pathlib import Path

import cv2

from vedit.graphics.compose import BEHIND_TRACK, SCENE_TRACKS
from vedit.graphics.faces import FaceTrack
from vedit.project import Project, ProjectError, find_project
from vedit.report import Report, VeditError
from vedit.review import flags as fl
from vedit.review import sheet
from vedit.review.capture import capture, zoom_at
from vedit.run import log_path
from vedit.words import Edl

EPILOG = "example: vedit review"


def add_args(sp) -> None:
    sp.add_argument("--force", action="store_true", help="snapshot again even when the build is unchanged")
    sp.epilog = EPILOG


def _load(ns):
    try:
        project = Project.load(find_project(override=ns.project))
    except ProjectError as e:
        raise VeditError(str(e), next="vedit new <video>  (or: vedit review --project PATH)") from e
    paths = project.paths
    edl_f = paths.edl / "edl.json"
    if not edl_f.is_file():
        raise VeditError(f"{edl_f} is not built yet", next="vedit cut")
    return project, paths, Edl.load(edl_f)


def face_box(track: FaceTrack | None, zooms, t: float):
    """The face [x0, y0, x1, y1] on screen at program second t (punch-in applied), or None."""
    if track is None:
        return None
    row = track.at(t)
    if not row.get("box"):
        return None
    return fl.zoomed(fl.xywh_to_box(row["box"]), zoom_at(zooms, t))


def judge(snap, track) -> list[dict]:
    """One row per graphic in time order: peak, sheet/cell, flags, texts, marks to draw."""
    rows = []
    for i, h in enumerate(snap.hosts):
        t = snap.peaks.get(h.id, h.start)
        snum, cell = sheet.where(i)
        tl = snap.timelines.get(h.id) or {}
        flags: list[fl.Flag] = []
        d = fl.drawing_flag(tl.get("tweens") or [], h.dur)
        if d:
            flags.append(d)
        texts = snap.texts.get(h.id)
        shot = snap.shots.get(h.id)
        # full-frame scenes cover the blurred A-roll; big words sit behind the cut-out by design
        on_footage = h.track not in SCENE_TRACKS and h.track != BEHIND_TRACK
        fb = face_box(track, snap.zooms, t) if on_footage else None
        rgb = None
        if shot is not None:
            img = cv2.imread(str(shot))
            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB) if img is not None else None
            if rgb is not None and rgb.shape[1] != 1920:
                rgb = cv2.resize(rgb, (1920, 1080), interpolation=cv2.INTER_AREA)
        measured = []
        if texts is not None:
            tf, measured = fl.text_flags(texts, fb, rgb)
            flags = tf + flags
        marks = {"text": [], "face": None}
        if any(f.code == "face" for f in flags) and fb:
            marks["face"] = fl.grow(fb, fl.FACE_MARGIN)
        if any(f.code in ("face", "small", "contrast") for f in flags):
            marks["text"] = [m["box"] for m in measured if _bad(m, marks["face"])]
        rows.append(
            {
                "id": h.id,
                "start": round(h.start, 3),
                "dur": round(h.dur, 3),
                "peak": round(t, 3),
                "sheet_no": snum,
                "cell": cell,
                "flags": [f.to_dict() for f in flags],
                "measured": texts is not None,
                "texts": measured,
                "shot": str(shot) if shot else None,
                "marks": marks,
            }
        )
    return rows


def _bad(m: dict, near) -> bool:
    small = m.get("px") is not None and float(m["px"]) < fl.MIN_TEXT_PX
    low = m.get("contrast") is not None and m["contrast"] < fl.MIN_CONTRAST
    return small or low or bool(near and fl.overlap(m["box"], near))


def review_outputs(paths, r: Report, listed: set[str] | None = None) -> list[dict]:
    """HUD flags for every built non-16:9 output, plus a HUD mock sheet when its draft exists."""
    from vedit.formats import hudcheck

    rows = []
    for hf in sorted((Path(paths.vedit) / "out").glob("*/hf")):
        if not (hf / "manifest.json").is_file() or (listed is not None and hf.parent.name not in listed):
            continue
        out, flags = hudcheck.check_output(hf)
        row = {"id": out["id"], "platforms": out["platforms"], "hud": flags}
        for f in flags:
            r.warn(
                f"{out['id']}: {f['id']} enters {f['platform']} {f['region']} ({f['share']:.0%} of it)  [hud]"
            )
        if not flags:
            r.ok_(f"{out['id']}: nothing enters the HUD of {', '.join(out['platforms'])}")
        draft = Path(paths.renders) / f"draft-{out['id']}.mp4"
        if draft.is_file():
            img = hudcheck.mock_sheet(
                draft, out["platforms"], Path(paths.vedit) / "review" / f"hud-{out['id']}.jpg"
            )
            row["mock"] = str(img)
            r.artifact(img, "image")
        rows.append(row)
    return rows


def run(ns) -> Report:
    project, paths, edl = _load(ns)
    review = Path(paths.vedit) / "review"
    log = log_path(paths.root, "review")
    snap = capture(Path(paths.hf), review, log, force=ns.force)
    try:
        track = FaceTrack.load(paths, list(project.sources), edl)
    except VeditError:
        track = None
    rows = judge(snap, track)
    files = sheet.write(rows, review, project.slug or paths.root.name)
    for r_ in rows:
        r_["sheet"] = str(files[r_["sheet_no"] - 1])
    r = Report("review")
    for f in files:
        r.artifact(f, "image")
    flagged = [x for x in rows if x["flags"]]
    unmeasured = [x["id"] for x in rows if not x["measured"]]
    r.ok_(
        f"{len(rows)} graphics at their peak on {len(files)} sheet(s) in {review} "
        f"(snapshots {'cached' if snap.cache_hit else 'taken'}); {len(flagged)} flagged"
    )
    if track is None:
        r.warn("no face track: the face check was skipped (run: vedit faces)")
    if unmeasured:
        r.warn(f"text not measured for {len(unmeasured)}: {', '.join(unmeasured[:6])}")
    for x in flagged:
        r.warn(f"{x['id']} {sheet.mmss(x['peak'])}  {Path(x['sheet']).name} cell {x['cell']}")
        for f in x["flags"]:
            r.info(f"    {f['code']}: {f['message']}")
    report_f = review / "report.json"
    cues = [{k: v for k, v in x.items() if k not in ("marks", "sheet_no")} for x in rows]
    data = {
        "sheets": [str(f) for f in files],
        "cache_hit": snap.cache_hit,
        "flagged": len(flagged),
        "cues": cues,
        "report": str(report_f),
    }
    data["outputs"] = review_outputs(paths, r, {o.id for o in project.outputs})
    hud = sum(len(o["hud"]) for o in data["outputs"])
    report_f.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    r.data = data
    r.next = (
        "look at the flagged cells first, fix cues.yaml or the style, then: vedit build"
        if flagged or hud
        else f"look at {files[0]}, then: vedit draft"
    )
    return r
