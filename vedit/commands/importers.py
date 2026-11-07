"""vedit importers: the importer plugins found in the config folder, or which one (if any) knows a path."""

from __future__ import annotations

from pathlib import Path

from vedit import importers as imps
from vedit.report import Report

EPILOG = "example: vedit importers ~/Recordings/talk.rec   |   vedit guide importers"


def add_args(sp) -> None:
    sp.add_argument("path", nargs="?", metavar="PATH", help="say which importer reads this path")
    sp.epilog = EPILOG


def run(ns) -> Report:
    r = Report("importers")
    found = imps.load()
    r.data = {
        "dirs": [str(d) for d in imps.dirs()],
        "importers": [{"name": i.name, "file": str(i.file), "about": i.about} for i in found],
    }
    if not found:
        r.ok_("no importer plugins: vedit new takes plain video files")
        r.info(f"add one as a .py file in {imps.chan.config_dir() / 'importers'}")
    for i in found:
        r.info(f"{i.name:<12} {i.about}  ({i.file})")
    if ns.path:
        hit = imps.recognise(Path(ns.path).expanduser())
        if hit:
            imp, rec = hit
            cam = (
                f", clean camera: {len(rec.camera.tracks)} file(s), {len(rec.camera.trims)} trims"
                if rec.camera
                else ""
            )
            r.ok_(f"{ns.path}: read by '{imp.name}' -> video {rec.video}{cam}")
            r.data["match"] = {"importer": imp.name, "video": str(rec.video), "camera": bool(rec.camera)}
        else:
            r.ok_(f"{ns.path}: no importer knows it; vedit new treats it as a plain video file")
            r.data["match"] = None
    r.next = "vedit guide importers"
    return r
