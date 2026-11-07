"""vedit clean: free disk without losing the edit. `--posted` also removes renders, media and the originals."""

import json
import os
import shutil
from pathlib import Path

from vedit import state
from vedit.ingest.cap import CAP_RECORDINGS, DEFAULT_SEARCH, EXPORT_EXTS, _search_dirs
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


def cap_pretty_name(cap: Path) -> str | None:
    try:
        name = json.loads((cap / "recording-meta.json").read_text(encoding="utf-8")).get("pretty_name")
    except (OSError, ValueError, AttributeError):
        return None
    return str(name) if name else None


def _cap_root(p: Path) -> Path | None:
    p = p.resolve()
    for c in (p, *p.parents):
        if c.suffix == ".cap" and c.is_dir():
            return c
    return None


def find_caps(project: Project, recordings: Path = CAP_RECORDINGS) -> list[Path]:
    """The .cap folders behind the project's cap sources: the one project.yaml names, plus any .cap in the
    Cap recordings folder whose recording-meta.json `pretty_name` is the same."""
    found: dict[Path, None] = {}
    for s in project.sources.values():
        if not s.cap:
            continue
        root = _cap_root(s.cap)
        if root is None:
            continue
        found[root] = None
        name = cap_pretty_name(root)
        if name and recordings.is_dir():
            for c in sorted(recordings.glob("*.cap")):
                if c.is_dir() and c.resolve() != root and cap_pretty_name(c) == name:
                    found[c.resolve()] = None
    return list(found)


def find_exports(project: Project, caps: list[Path], search=DEFAULT_SEARCH) -> list[Path]:
    """Cap exports (`<pretty_name>.mp4` in the search dirs) and src/ links to files outside the .cap folders."""
    out: dict[Path, None] = {}
    names = {n for c in caps if (n := cap_pretty_name(c))}
    for d in _search_dirs(search):
        for n in names:
            for ext in EXPORT_EXTS:
                if (d / f"{n}{ext}").is_file():
                    out[(d / f"{n}{ext}").resolve()] = None
    return [p for p in out if not any(_inside(p, c) for c in caps)]


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


def original_targets(
    project: Project, recordings: Path = CAP_RECORDINGS
) -> tuple[list[tuple[Path, str]], list[Path]]:
    """(originals to delete, exports that are APFS clones and free nothing)."""
    root = project.root
    out: list[tuple[Path, str]] = []
    caps = find_caps(project, recordings)
    for c in caps:
        out.append((c, f"Cap original (.cap, pretty_name '{cap_pretty_name(c)}')"))
    for s in project.sources.values():
        if s.file:
            f = s.file.resolve()
            if f == root or _inside(root, f) or (_inside(f, root) and not _inside(f, project.paths.src)):
                continue  # never the project folder or its kept files
            out.append((f, f"source file {s.name}"))
    return out, find_exports(project, caps)


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
            r.info(f"  {'~0':>9}  {e}  (Cap export, APFS clone, frees ~0, kept)")
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
