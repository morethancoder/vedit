"""vedit clean: free disk without losing the edit. `--posted` also removes renders, media and the originals."""

import os
import shutil
from pathlib import Path

from vedit import importers, state
from vedit.project import Project, ProjectError, find_project
from vedit.report import Report, VeditError, confirm

EPILOG = "example: vedit clean --posted --dry-run"


def add_args(sp) -> None:
    sp.add_argument(
        "--posted", action="store_true", help="also delete renders, proxies, program, cut-outs and originals"
    )
    sp.epilog = EPILOG


def disk_bytes(path: Path) -> int:
    """Real allocated bytes (like du): st_blocks, symlinks not followed, each inode counted once.

    APFS clones share blocks with their original, so deleting a clone frees less than this number."""
    seen: set[tuple[int, int]] = set()

    def one(p: Path) -> int:
        try:
            st = p.lstat()
        except OSError:
            return 0
        key = (st.st_dev, st.st_ino)
        if key in seen:
            return 0
        seen.add(key)
        total = st.st_blocks * 512
        if p.is_dir() and not p.is_symlink():
            try:
                for e in os.scandir(p):
                    total += one(Path(e.path))
            except OSError:
                pass
        return total

    return one(Path(path))


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def always_targets(paths) -> list[tuple[Path, str]]:
    v = paths.vedit
    t: list[tuple[Path, str]] = [
        (v / "cache" / "frames", "HyperFrames frame caches"),
        (paths.renders / "chunks", "4K render chunks"),
        (v / "tmp", "scratch"),
        (v / "review" / "cache", "review snapshot cache"),
        (v / "review" / "hf", "review project copy"),
    ]
    t += [(p, "scratch audio") for p in sorted((v / "listen").glob("*.wav"))]
    t += [(p, "scratch images") for p in sorted((v / "build").glob("snaps*"))]
    t += [(v / "build" / "tcmp", "scratch images")]
    return [(p, why) for p, why in t if p.exists() or p.is_symlink()]


def posted_targets(paths) -> list[tuple[Path, str]]:
    t = [
        (paths.renders, "renders (draft, master)"),
        (paths.media, "proxies and camera files"),
        (paths.program, "program mp4/wav/pieces"),
        (paths.mattes, "cut-out mattes"),
    ]
    return [(p, why) for p, why in t if p.exists()]


def original_targets(project: Project) -> tuple[list[tuple[Path, str]], list[Path]]:
    """(originals to delete with why, files kept). A source's recorder project (`origin`) is listed by its
    importer's `originals()` when it has one, else as itself; edited videos outside it are kept (often clones
    that free nothing). Plain `file:`/`camera:` sources outside the project are listed."""
    root = project.root
    out: dict[Path, str] = {}
    kept: dict[Path, None] = {}
    for s in project.sources.values():
        origin = s.origin.resolve() if s.origin and s.origin.exists() else None
        if s.origin is not None:
            imp = importers.get(s.importer)
            got = imp.originals(s.origin) if imp else None
            if got is not None:
                dele, keep = got
                out.update({Path(p).resolve(): why for p, why in dele})
                kept.update({Path(p).resolve(): None for p in keep})
            elif origin:
                out[origin] = f"recording project of source {s.name}" + (
                    f" ({s.importer})" if s.importer else ""
                )
        for f in (s.file, *s.camera):
            f = f.resolve()
            if f == root or _inside(root, f) or (_inside(f, root) and not _inside(f, project.paths.src)):
                continue  # never the project folder or its kept files
            if origin and _inside(f, origin):
                continue  # goes with its recording project
            if s.origin is not None:
                kept[f] = None
            else:
                out[f] = f"source file {s.name}"
    return list(out.items()), [k for k in kept if k not in out]


def delete(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    else:
        shutil.rmtree(path)


def prune_src(paths) -> None:
    """Drop src/ links whose target is gone, so the project does not point at deleted files."""
    if paths.src.is_dir():
        for p in paths.src.iterdir():
            if p.is_symlink() and not p.exists():
                p.unlink()


def run(ns) -> Report:
    try:
        root = find_project(override=ns.project)
        project = Project.load(root)
    except ProjectError as e:
        raise VeditError(str(e), next="vedit clean --project PATH") from e
    paths = project.paths
    if state.job_state(paths) == "running" and not ns.dry_run:
        raise VeditError(
            "a job is running; clean would pull files from under it",
            next="vedit wait  (then run vedit clean)",
            code="busy",
        )
    r = Report("clean")
    targets = always_targets(paths)
    clones: list[Path] = []
    if ns.posted:
        targets += posted_targets(paths)
        orig, clones = original_targets(project)
        targets += orig
    rows = [{"path": str(p), "why": why, "bytes": disk_bytes(p)} for p, why in targets]
    total = sum(x["bytes"] for x in rows)
    r.data = {
        "posted": bool(ns.posted),
        "dry_run": bool(ns.dry_run),
        "targets": rows,
        "freed_bytes": 0,
        "deleted": False,
    }

    if not rows:
        r.ok_("nothing to clean")
        return r
    dangerous = bool(ns.posted)
    r.step(("would delete" if ns.dry_run or dangerous else "deleting") + f" ({human(total)})")
    if dangerous or ns.dry_run:
        for x in rows:
            r.info(f"  {human(x['bytes']):>9}  {x['path']}  ({x['why']})")
        for e in clones:
            r.info(f"  {'~0':>9}  {e}  (edited video outside the recording project, kept)")
        r.info("sizes are allocated bytes; APFS clones share blocks, so freed space can be smaller")
    if ns.dry_run:
        r.ok_(f"dry run: nothing deleted ({human(total)} would be listed)")
        return r
    if dangerous and not confirm(
        "Delete all of the above? The originals cannot be recovered.", ns.yes, destructive=True
    ):
        r.warn(
            "nothing deleted: not confirmed"
            + ("" if ns.yes else " (no TTY? pass --yes after the upload is posted)")
        )
        r.next = "vedit clean --posted --yes"
        return r

    freed = 0
    for (p, _), x in zip(targets, rows):
        try:
            delete(p)
        except OSError as e:
            r.fail(f"{p}: {e}")
            continue
        freed += x["bytes"]
        if not dangerous:
            r.ok_(f"removed {p}  ({human(x['bytes'])})")
    if dangerous:
        prune_src(paths)
        r.ok_(f"removed {len(rows)} paths")
    r.ok_(f"freed {human(freed)}")
    r.data.update(freed_bytes=freed, deleted=True)
    return r
