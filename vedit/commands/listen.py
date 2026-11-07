"""vedit listen: what does the audio say here (an excerpt, candidate splices, or program times)."""

from __future__ import annotations

from pathlib import Path

from vedit.cut import splice
from vedit.project import Project, ProjectError, find_project
from vedit.report import Report, VeditError

EPILOG = "example: vedit listen --splice A 668.78:672.2 A 668.78:674.1"
HELP = "vedit listen --help"


def add_args(sp) -> None:
    mode = sp.add_mutually_exclusive_group()
    mode.add_argument(
        "--splice", action="store_true", help="items are CLIP IN:OUT pairs: hear each candidate join"
    )
    mode.add_argument("--program", action="store_true", help="items are program times T or S:E")
    sp.add_argument(
        "items", nargs="*", metavar="ITEM", help="CLIP START END | --splice CLIP IN:OUT ... | --program T ..."
    )
    sp.epilog = EPILOG


def _num(text: str) -> float:
    try:
        return float(text)
    except ValueError:
        raise VeditError(f"not a time in seconds: {text!r}", next=HELP) from None


def _range(text: str) -> tuple[float, float]:
    a, sep, b = text.partition(":")
    if not sep:
        raise VeditError(f"expected START:END, got {text!r}", next=HELP)
    s, e = _num(a), _num(b)
    if e <= s:
        raise VeditError(f"range {text!r} ends before it starts", next=HELP)
    return s, e


def parse(ns) -> tuple[str, list[tuple]]:
    """Return (mode, requests). Requests: excerpt (clip, s, e); splice (clip, in, out); program (label, s, e)."""
    items = list(ns.items)
    if ns.splice:
        if not items or len(items) % 2:
            raise VeditError("--splice takes CLIP IN:OUT pairs", next="vedit listen --splice A 668.78:672.2")
        return "splice", [(items[i], *_range(items[i + 1])) for i in range(0, len(items), 2)]
    if ns.program:
        if not items:
            raise VeditError("--program takes one or more program times", next="vedit listen --program 412.5")
        reqs = []
        for it in items:
            if ":" in it:
                reqs.append((it, *_range(it)))
            else:
                t = _num(it)
                reqs.append((it, max(0.0, t - splice.PROGRAM_SIDE), t + splice.PROGRAM_SIDE))
        return "program", reqs
    if len(items) != 3:
        raise VeditError("expected CLIP START END", next="vedit listen A 300 312")
    s, e = _num(items[1]), _num(items[2])
    if e <= s:
        raise VeditError("END must be after START", next="vedit listen A 300 312")
    return "excerpt", [(items[0], s, e)]


def _find(ns) -> Project:
    try:
        return Project.load(find_project(override=ns.project))
    except ProjectError as e:
        raise VeditError(str(e), next="vedit new <cap-project>  (or: vedit listen --project PATH)") from e


def _wav(project: Project, clip: str) -> Path:
    if clip not in project.sources:
        names = ", ".join(sorted(project.sources))
        raise VeditError(f"no clip {clip!r} (clips: {names})", next="vedit status")
    wav = project.paths.media / f"{clip}-48k.wav"
    if not wav.is_file():
        raise VeditError(
            f"missing {wav}", next=f"vedit new <input> --dir {project.root.parent}  (rebuilds media)"
        )
    return wav


def _text(ws: list[splice.Heard]) -> str:
    return " ".join(w.text for w in ws)


def _program(project: Project, reqs: list[tuple], r: Report) -> list[dict]:
    wav = project.paths.program / "program.wav"
    if not wav.is_file():
        raise VeditError(f"{wav} is not built yet", next="vedit cut")
    audio, sr = splice.read_wav(wav)
    pieces = [splice.cut(audio, sr, s, e) for _, s, e in reqs]
    heard = splice.listen(project, pieces, sr, name="pprobe", gap=splice.PROGRAM_GAP)
    out = []
    for (label, s, e), ws in zip(reqs, heard, strict=True):
        out.append({"at": label, "start": s, "end": e, "text": _text(ws)})
        r.info(f"{label:>14}  {out[-1]['text']}")
    return out


def _clips(project: Project, mode: str, reqs: list[tuple], r: Report) -> list[dict]:
    audios = {c: splice.read_wav(_wav(project, c)) for c in dict.fromkeys(q[0] for q in reqs)}
    srs = {sr for _, sr in audios.values()}
    if len(srs) != 1:
        raise VeditError(f"clips have different sample rates: {sorted(srs)}", next="vedit new <input>")
    sr = srs.pop()
    if mode == "splice":
        pieces = [splice.splice_piece(audios[c][0], sr, s, e) for c, s, e in reqs]
        heard = splice.listen(project, pieces, sr, name="probe")
        out = []
        for (c, s, e), ws in zip(reqs, heard, strict=True):
            out.append({"clip": c, "in": s, "out": e, "text": _text(ws)})
            r.info(f"{f'{c} {s:g}:{e:g}':>18}  {out[-1]['text']}")
        return out
    ((c, s, e),) = reqs
    ws = splice.listen(project, [splice.cut(audios[c][0], sr, s, e)], sr, name="stamps")[0]
    words = [{"t0": round(s + w.start, 3), "t1": round(s + w.end, 3), "w": w.text} for w in ws]
    r.info(" | ".join(f"{w['t0']:.2f}-{w['t1']:.2f} {w['w']}" for w in words) or "(nothing heard)")
    return [{"clip": c, "start": s, "end": e, "words": words}]


def run(ns) -> Report:
    mode, reqs = parse(ns)
    project = _find(ns)
    r = Report("listen")
    results = _program(project, reqs, r) if mode == "program" else _clips(project, mode, reqs, r)
    r.data = {"mode": mode, "results": results}
    return r
