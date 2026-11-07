"""vedit draft: render `.vedit/hf/` at 1080p (draft quality) to `.vedit/renders/draft.mp4`, check it, open it
in QuickTime. Same full-frame composition the 4K master renders. Never starts a HyperFrames Studio preview.

Rendered chunk by chunk (`.vedit/hf/chunks/chunk-NN.html`, the same cuts as the 4K master) when the build wrote
chunks: a frame of the whole-film composition carries all its graphics and captured 1.7x slower than the same
frame from its chunk (2026-11-06). Finished chunks stay in `.vedit/renders/draft-parts/` with a key, so a rerun
renders only the chunks whose HTML or shared files changed; the parts are joined losslessly (audio re-encoded once).
"""

from __future__ import annotations

import itertools
import json
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from vedit import state
from vedit.project import Project, ProjectError, find_project
from vedit.render import master
from vedit.render.hf import render_cmd, render_env
from vedit.report import Report, VeditError
from vedit.run import RunError, ffprobe_duration, ffprobe_json, hash_of, log_path, sample_hash
from vedit.run import run as sh

EPILOG = "example: vedit draft --no-open"
RENDER_TIMEOUT = 4 * 3600
DURATION_TOLERANCE = 1.0  # seconds: draft vs program
# chunks rendered at once: 1080p draft throughput 1.67x with 2, 1.78x with 3 (2026-11-06); 2 keeps memory low
PARALLEL = 2
SKIP_DIRS = {".hyperframes", "chunks"}  # chunks/ and chunks.json only feed the 4K render
SKIP_FILES = {"chunks.json"}


def add_args(sp) -> None:
    sp.add_argument("--force", action="store_true", help="render again even if the build is unchanged")
    sp.add_argument("--no-open", action="store_true", help="do not open the draft in QuickTime")
    sp.add_argument(
        "--output",
        action="append",
        metavar="ID",
        help="draft this output (repeat; `all`); default: the 16:9 film",
    )
    sp.epilog = EPILOG


def hf_hash(hf: Path, *, shared_only: bool = False) -> str:
    """Content hash of the HyperFrames project: paths + file bytes; linked media by sample hash.
    `shared_only`: without `index.html`, i.e. what every chunk reads besides its own HTML."""
    parts: list = []
    skip = SKIP_FILES | ({"index.html"} if shared_only else set())
    for dirpath, dirs, files in os.walk(hf):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for name in sorted(files):
            if name in skip and Path(dirpath) == hf:
                continue
            f = Path(dirpath) / name
            rel = str(f.relative_to(hf))
            if f.is_symlink() or f.stat().st_size > (8 << 20):
                parts.append([rel, sample_hash(f.resolve())])
            else:
                parts.append([rel, hash_of(f)])
    return hash_of(parts)


def clean_work(renders: Path) -> None:
    """Remove HyperFrames scratch left in renders/ (work dirs, transactions) after a render, ok or not."""
    for pat in ("work-*", ".*hf-transaction-*"):
        for d in renders.glob(pat):
            shutil.rmtree(d, ignore_errors=True)


def verify(mp4: Path, program_s: float | None) -> tuple[float, bool]:
    """(duration, has audio); raises when the file is unreadable or its length is off."""
    try:
        info = ffprobe_json(mp4)
    except (RunError, ValueError) as e:
        raise VeditError(f"{mp4} is not a readable video: {e}", next="vedit draft --force") from e
    dur = float(info["format"]["duration"])
    audio = any(s.get("codec_type") == "audio" for s in info.get("streams", []))
    if program_s is not None and abs(dur - program_s) > DURATION_TOLERANCE:
        raise VeditError(
            f"draft is {dur:.1f}s but the program is {program_s:.1f}s", next="vedit draft --force"
        )
    return dur, audio


def draft_chunks(hf: Path) -> list[tuple[Path, float]] | None:
    """[(chunk html, seconds)] from the build's chunks.json, or None (no chunks: render the whole index.html)."""
    try:
        bounds = json.loads((hf / "chunks.json").read_text())["bounds"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    out = [
        (hf / "chunks" / f"chunk-{i:02d}.html", b - a) for i, (a, b) in enumerate(itertools.pairwise(bounds))
    ]
    return out if out and all(p.is_file() for p, _ in out) else None


def stale_chunks(
    hf: Path, chunks: list[tuple[Path, float]], parts: Path
) -> list[tuple[Path, float, Path, str]]:
    """(html, seconds, part mp4, key) of every chunk whose kept part is missing or keyed differently."""
    shared = hf_hash(hf, shared_only=True)
    todo = []
    for html, sec in chunks:
        mp4 = parts / (html.stem + ".mp4")
        kf = mp4.with_suffix(".key")
        key = hash_of(html.read_text(), shared)
        if not (mp4.is_file() and kf.is_file() and kf.read_text() == key):
            todo.append((html, sec, mp4, key))
    return todo


def render_chunks(
    hf: Path, chunks: list[tuple[Path, float]], parts: Path, out: Path, log: Path
) -> tuple[int, int]:
    """Render the stale chunks into `parts/` (each keyed, PARALLEL at a time), join all of them into `out`.
    Returns (rendered, reused)."""
    parts.mkdir(parents=True, exist_ok=True)
    files = [parts / (html.stem + ".mp4") for html, _ in chunks]
    secs = [sec for _, sec in chunks]
    todo = stale_chunks(hf, chunks, parts)
    for *_, mp4, _key in todo:
        mp4.with_suffix(".key").unlink(missing_ok=True)

    def one(html: Path, sec: float, mp4: Path, key: str) -> None:
        tmp = mp4.with_suffix(".tmp.mp4")
        tmp.unlink(missing_ok=True)
        cmd = render_cmd(hf, tmp, composition=f"chunks/{html.name}")
        sh(cmd, timeout=RENDER_TIMEOUT, cwd=hf, log=log, env=render_env(parallel_stream=True))
        got = ffprobe_duration(tmp)
        if got is None or abs(got - sec) > DURATION_TOLERANCE:
            tmp.unlink(missing_ok=True)
            raise VeditError(f"draft {html.stem} is {got}s, expected {sec:.1f}s", next="vedit draft --force")
        tmp.replace(mp4)
        mp4.with_suffix(".key").write_text(key)

    with ThreadPoolExecutor(PARALLEL) as pool:
        for f in [pool.submit(one, *t) for t in todo]:
            f.result()  # the first failure raises (after the running chunks finish)
    keep = {f.name for f in files} | {f.with_suffix(".key").name for f in files}
    for f in parts.iterdir():  # chunks of an older, longer build
        if f.is_file() and f.name not in keep:
            f.unlink(missing_ok=True)
    joined = master.join(files, secs, out, parts / "join", log)
    joined.replace(out)
    shutil.rmtree(parts / "join", ignore_errors=True)
    return len(todo), len(chunks) - len(todo)


def _size_mb(p: Path) -> float:
    return round(p.stat().st_size / 1e6, 1)


def pick_outputs(project, ids: list[str]) -> list:
    known = {o.id: o for o in project.outputs if o.aspect != "16:9"}
    if "all" in ids:
        return list(known.values())
    for i in ids:
        if i not in known:
            raise VeditError(f"no non-16:9 output called {i!r} (have: {', '.join(known) or 'none'})",
                             next="vedit output list", code="bad_input")  # fmt: skip
    return [known[i] for i in ids]


def run_outputs(ns, project, final: bool) -> Report:
    """Draft (or final render) of the chosen non-16:9 outputs, one after the other."""
    from vedit.formats import render_out

    paths = project.paths
    r = Report("render" if final else "draft")
    log = log_path(paths.root, "render" if final else "draft")
    for o in pick_outputs(project, ns.output):
        t = time.monotonic()
        res = render_out.render(paths, project, o, final, log, force=getattr(ns, "force", False))
        how = "unchanged, kept" if res["reused"] else f"rendered in {time.monotonic() - t:.0f}s"
        r.ok_(f"{o.id}: {res['file']} ({how})")
        r.artifact(res["file"], "video")
        for seg in res.get("segments") or []:
            r.artifact(seg, "video")
        if res.get("segments"):
            r.info(f"{o.id}: {len(res['segments'])} story segments")
        r.data.setdefault("outputs", []).append(res)
        if not final and not getattr(ns, "no_open", False) and len(ns.output) == 1:
            sh(["open", "-a", "QuickTime Player", res["file"]], timeout=30, check=False)
    r.next = "vedit review  (HUD check on the drafts)" if not final else "vedit status"
    return r


def run(ns) -> Report:
    try:
        project = Project.load(find_project(override=ns.project))
    except ProjectError as e:
        raise VeditError(str(e), next="vedit build  (or: vedit draft --project PATH)") from e
    paths = project.paths
    if getattr(ns, "output", None):
        return run_outputs(ns, project, final=False)
    hf = paths.hf
    if not (hf / "index.html").is_file():
        raise VeditError(f"{hf / 'index.html'} is not built yet", next="vedit build")
    mp4 = paths.renders / "draft.mp4"
    proxy = paths.program / "proxy.mp4"
    program_s = ffprobe_duration(proxy) if proxy.is_file() else None
    key = hf_hash(hf)
    prev = state.load(paths)["stages"].get("draft", {})
    r = Report("draft")
    skipped = not ns.force and mp4.is_file() and prev.get("inputs") == key
    if getattr(ns, "dry_run", False):
        chunks = draft_chunks(hf)
        r.step(f"draft  ({mp4})")
        if skipped:
            r.ok_("dry run: the build is unchanged; the existing draft would be reused")
            todo = []
        elif chunks:
            todo = stale_chunks(hf, chunks, paths.renders / "draft-parts") if not ns.force else chunks
            secs = sum(c[1] for c in todo)
            r.info(f"would render {len(todo)} of {len(chunks)} chunks ({secs:.0f}s of film), then join")
            r.ok_("dry run: nothing rendered")
        else:
            todo = None
            r.info(f"would render the whole composition ({program_s or 0:.0f}s of film)")
            r.ok_("dry run: nothing rendered")
        r.data = {"dry_run": True, "reuse_draft": skipped,
                  "chunks": len(chunks) if chunks else None,
                  "to_render": len(todo) if todo is not None else None}  # fmt: skip
        r.next = "vedit draft"
        return r
    took = 0.0
    counts: tuple[int, int] | None = None
    if skipped:
        r.info("build unchanged: reusing the existing draft (--force to render again)")
        took = float(prev.get("seconds", 0.0))
    else:
        paths.renders.mkdir(parents=True, exist_ok=True)
        part = paths.renders / "draft.part.mp4"  # the old draft stays until a new one is verified
        part.unlink(missing_ok=True)
        log = log_path(paths.root, "draft")
        state.start_job(paths, "draft", os.getpid(), log, command="vedit draft")
        t0 = time.monotonic()
        chunks = draft_chunks(hf)
        try:
            if chunks:
                counts = render_chunks(hf, chunks, paths.renders / "draft-parts", part, log)
            else:
                sh(render_cmd(hf, part), timeout=RENDER_TIMEOUT, cwd=hf, log=log,
                   env=render_env(parallel_stream=True))  # fmt: skip
            took = time.monotonic() - t0
            verify(part, program_s)
            part.replace(mp4)
        except VeditError:
            state.finish_job(paths, False)
            part.unlink(missing_ok=True)
            raise
        finally:
            clean_work(paths.renders)
            if (paths.renders / "draft-parts").is_dir():
                clean_work(paths.renders / "draft-parts")
        state.finish_job(paths, True)
        state.record_stage(paths, "draft", key, [mp4])
        data = state.load(paths)
        data["stages"]["draft"]["seconds"] = round(took, 1)
        state.save(paths, data)
    dur, audio = verify(mp4, program_s)
    if not audio:
        r.warn("the draft has no audio track")
    size = _size_mb(mp4)
    r.ok_(
        f"{mp4}: {dur / 60:.1f} min ({dur:.1f}s), {size:g} MB"
        + ("" if skipped else f", rendered in {took:.0f}s")
        + (f" ({counts[0]} chunk(s) rendered, {counts[1]} reused)" if counts else "")
    )
    opened = False
    if not ns.no_open:
        sh(["open", "-a", "QuickTime Player", str(mp4)], timeout=30, check=False)
        opened = True
        r.info("opened in QuickTime")
    r.data = {
        "mp4": str(mp4),
        "seconds": round(dur, 2),
        "program_seconds": round(program_s, 2) if program_s else None,
        "size_mb": size,
        "render_seconds": round(took, 1),
        "chunks": {"rendered": counts[0], "reused": counts[1]} if counts else None,
        "skipped": skipped,
        "audio": audio,
        "opened": opened,
    }
    r.artifact(mp4, "video")
    r.next = "vedit render  (once the draft is approved)"
    return r
