"""vedit transcribe: word-timed transcripts of every source clip through Studio (cached, detached)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from vedit import state, studio
from vedit.project import Paths, Project, ProjectError, find_project
from vedit.report import Report, VeditError
from vedit.run import hash_of, log_path
from vedit.words.norm import mixed_script

EPILOG = "example: vedit transcribe --clip A --force"
GAP, MAX_WORDS = 0.7, 18  # line grouping (ported from T tools/words.py)
MIXED_SHOWN = 8


def add_args(sp) -> None:
    sp.add_argument("--wait", action="store_true", help="work in the foreground (default: detached)")
    sp.add_argument("--clip", metavar="A", help="only this source clip")
    sp.add_argument("--force", action="store_true", help="redo even when cached")
    sp.epilog = EPILOG


def lines(ws: list[dict], gap: float = GAP, maxw: int = MAX_WORDS):
    cur = []
    for i, w in enumerate(ws):
        cur.append(w)
        nxt = ws[i + 1] if i + 1 < len(ws) else None
        if w["w"][-1:] in ".?!" or nxt is None or nxt["t0"] - w["t1"] > gap or len(cur) >= maxw:
            yield cur
            cur = []


def _mmss(t: float) -> str:
    return f"{int(t // 60):02d}:{t % 60:05.2f}"


def render_txt(ws: list[dict]) -> str:
    return "".join(
        f"{_mmss(g[0]['t0'])}–{_mmss(g[-1]['t1'])}  {' '.join(w['w'] for w in g)}\n" for g in lines(ws)
    )


def mixed_words(paths: Paths, clip: str) -> list[dict]:
    """Words of the saved transcript that mix Arabic and Latin letters: [{"t": t0, "w": word}]."""
    try:
        ws = json.loads((paths.words / f"{clip}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [{"t": w["t0"], "w": w["w"]} for w in ws if mixed_script(w["w"])]


def _warn_mixed(r: Report, clip: str, mixed: list[dict]) -> None:
    if not mixed:
        return
    shown = "; ".join(f"{clip} {m['t']:g} {m['w']}" for m in mixed[:MIXED_SHOWN])
    more = f"; … and {len(mixed) - MIXED_SHOWN} more" if len(mixed) > MIXED_SHOWN else ""
    r.warn(f"{clip}: {len(mixed)} mixed Arabic/Latin token(s), likely ASR glitches: {shown}{more}")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _meta(paths: Paths, clip: str) -> Path:
    return paths.words / f"{clip}.meta.json"


def _key(stage_inputs: str | None, clip: str, wav: Path) -> str:
    return hash_of(stage_inputs or "", clip, str(wav), wav.stat().st_size)


def _is_cached(paths: Paths, clip: str, key: str) -> dict | None:
    try:
        meta = json.loads(_meta(paths, clip).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    ok = meta.get("key") == key and all((paths.words / f"{clip}.{e}").is_file() for e in ("json", "txt"))
    return meta if ok else None


def _find(ns) -> tuple[Path, Project]:
    try:
        root = find_project(override=ns.project)
        return root, Project.load(root)
    except ProjectError as e:
        raise VeditError(str(e), next="vedit new <video>  (or: vedit transcribe --project PATH)") from e


def _spawn(ns, root: Path, paths: Paths, n: int) -> int:
    cmd = [sys.executable, "-m", "vedit", "transcribe", "--wait", "--project", str(root)]
    if ns.clip:
        cmd += ["--clip", ns.clip]
    if ns.force:
        cmd.append("--force")
    log = log_path(root, "transcribe")
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "ab") as out:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=out,
            start_new_session=True,
            env={**os.environ, "VEDIT_JOB": "1"},
        )
    state.start_job(paths, "transcribe", proc.pid, log, command=" ".join(cmd), clips=n, clip=0)
    return proc.pid


def run(ns) -> Report:
    root, project = _find(ns)
    paths = project.paths
    names = sorted(project.sources)
    if ns.clip:
        if ns.clip not in project.sources:
            raise VeditError(f"no clip {ns.clip!r} (clips: {', '.join(names)})", next="vedit status")
        names = [ns.clip]
    wavs = {}
    for n in names:
        wav = paths.media / f"{n}-48k.wav"
        if not wav.is_file():
            raise VeditError(
                f"missing {wav}", next=f"vedit new <input> --dir {root.parent}  (rebuilds media)"
            )
        wavs[n] = wav
    stage_inputs = state.current_inputs(project, paths, state.load(paths)["stages"])["transcribe"]
    keys = {n: _key(stage_inputs, n, wavs[n]) for n in names}
    todo = [n for n in names if ns.force or not _is_cached(paths, n, keys[n])]

    r = Report("transcribe")
    job = state.load(paths)["job"]
    if todo and not ns.wait:
        if state.job_state(paths) == "running" and job and job.get("stage") == "transcribe":
            r.warn(f"a transcribe job is already running (pid {job.get('pid')}); not starting another")
            r.data = {"started": False, "running": True, "pid": job.get("pid")}
            r.next = "vedit status"
            return r
        pid = _spawn(ns, root, paths, len(names))
        r.step(f"{project.slug}  ({root})")
        r.ok_(f"transcribing {', '.join(todo)} in the background (pid {pid})")
        r.info(f"log: {log_path(root, 'transcribe')}")
        r.data = {"started": True, "pid": pid, "clips": todo}
        r.next = "vedit status"
        return r

    child = bool(os.environ.get("VEDIT_JOB")) and ns.wait
    ok = False
    try:
        r.step(f"{project.slug}  ({root})")
        report = []
        for i, n in enumerate(names):
            if child:
                state.update_progress(paths, clip=i, clips=len(names), current=n)
            report.append(_do_clip(paths, project, n, wavs[n], keys[n], n in todo, r))
        outputs = [paths.words / f"{n}.{e}" for n in names for e in ("json", "txt")]
        if not ns.clip or len(names) == len(project.sources):
            state.record_stage(paths, "transcribe", stage_inputs or "", outputs)
        if child:
            state.update_progress(paths, clip=len(names), clips=len(names), current=None)
        ok = True
    finally:
        if child:
            state.finish_job(paths, ok)
    r.data = {"clips": report}
    r.next = "vedit summarize"
    return r


def _do_clip(paths: Paths, project: Project, n: str, wav: Path, key: str, redo: bool, r: Report) -> dict:
    if not redo:
        meta = _is_cached(paths, n, key) or {}
        r.ok_(f"{n}: {meta.get('words', 0)} words, {meta.get('duration', 0):.1f}s, cached")
        mixed = mixed_words(paths, n)
        _warn_mixed(r, n, mixed)
        return {"clip": n, **meta, "cached": True, "mixed_script": mixed}
    log = log_path(paths.root, "transcribe")
    t = studio.transcribe(
        wav,
        project.lang,
        project.dialect,
        project.hint,
        fillers="keep",
        cache_dir=paths.studio,
        log=log,
    )
    ws = [{"t0": round(w.start, 3), "t1": round(w.end, 3), "w": w.text} for w in t.words]
    _write(paths.words / f"{n}.json", json.dumps(ws, ensure_ascii=False))
    _write(paths.words / f"{n}.txt", render_txt(ws))
    dur = ws[-1]["t1"] if ws else 0.0
    meta = {
        "key": key,
        "words": len(ws),
        "duration": dur,
        "model": t.model,
        "warnings": t.warnings,
        "studio_cached": t.cached,
    }
    _write(_meta(paths, n), json.dumps(meta, ensure_ascii=False))
    r.ok_(
        f"{n}: {len(ws)} words, {dur:.1f}s, model {t.model or 'auto'}"
        + (", Studio cache" if t.cached else "")
    )
    for w in t.warnings:
        r.warn(f"{n}: {w}")
    mixed = mixed_words(paths, n)
    _warn_mixed(r, n, mixed)
    return {"clip": n, **meta, "cached": False, "mixed_script": mixed}
