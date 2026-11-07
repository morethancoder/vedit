"""vedit summarize: summary.md (chapters, visual moments, likely ASR errors, names) drafted by a cheap model."""

from __future__ import annotations

import re
import time
from pathlib import Path

from vedit import llm, state
from vedit.commands.llm import report_usage, usage
from vedit.commands.transcribe import _find, _write
from vedit.report import Report, VeditError
from vedit.run import hash_of
from vedit.words import load as load_words

EPILOG = "example: vedit summarize --notes outline.txt"
AT_RE = re.compile(r"^\[?\s*([A-Za-z]\w*)?\s*(\d+(?:\.\d+)?)\s*s?\s*\]?$")


def add_args(sp) -> None:
    sp.add_argument("--notes", metavar="FILE", help="the speaker's outline, given to the model as context")
    sp.add_argument(
        "--model", default="auto", choices=["auto", *llm.MODELS], metavar="M", help="force a model"
    )
    sp.add_argument("--force", action="store_true", help="redo even when the transcript has not changed")
    sp.epilog = EPILOG


def fix_at(at: str, clips: dict[str, float]) -> str:
    """Normalise a model's `[A 12.6]` / `12.6` / `A 12.6s` to `A 12.6`; Invalid if it names no real time."""
    m = AT_RE.match(str(at).strip())
    if not m:
        raise llm.Invalid(f"time {at!r} is not 'clip seconds'")
    clip, t = m.group(1), float(m.group(2))
    if clip is None and len(clips) == 1:
        clip = next(iter(clips))
    if clip not in clips or t > clips[clip] + 1:
        raise llm.Invalid(f"time {at!r} is not in the transcript")
    return f"{clip} {t:.1f}"


def checker(clips: dict[str, float]):
    def check(value: dict, _text: str) -> None:
        for ch in value["chapters"]:
            ch["start"] = fix_at(ch["start"], clips)
            for b in ch["beats"]:
                b["at"] = fix_at(b["at"], clips)
        for key in ("visual_moments", "asr_errors"):
            for item in value[key]:
                item["at"] = fix_at(item["at"], clips)
        if not value["chapters"]:
            raise llm.Invalid("no chapters")

    return check


def render(value: dict, slug: str, model: str) -> str:
    out = [
        f"# Summary: {slug}",
        "",
        f"Drafted by {model} with `vedit summarize` on {time.strftime('%Y-%m-%d')}. Times are source times",
        "(`clip seconds`, the same as `near:` in cuts.yaml and cues.yaml). A draft: check it against the video.",
        "",
        "## Chapters",
        "",
    ]
    for i, ch in enumerate(value["chapters"], 1):
        out += [f"### {i}. {ch['title']}  ({ch['start']})", "", ch["about"], ""]
        out += [f"- {b['at']}  {b['text']}" for b in ch["beats"]]
        out.append("")
    out += ["## Visual moments", ""]
    for v in value["visual_moments"]:
        words = f'  ("{v["words"]}")' if v.get("words") else ""
        out.append(f"- {v['at']}  **{v['kind']}**: {v['show']}{words}")
    out += ["", "## Likely ASR errors", ""]
    out += [f"- {e['at']}  {e['heard']} -> {e['likely']}" for e in value["asr_errors"]] or ["- none spotted"]
    out += ["", "## Names and terms", ""]
    out += [f"- **{t['term']}**: {t['note']}" for t in value["terms"]] or ["- none"]
    return "\n".join(out) + "\n"


def run(ns) -> Report:
    root, project = _find(ns)
    paths = project.paths
    for clip in project.sources:
        if not (paths.words / f"{clip}.json").is_file():
            raise VeditError(f"no transcript for clip {clip}", next="vedit transcribe")
    notes = Path(ns.notes).read_text(encoding="utf-8") if ns.notes else None
    words = {c: load_words(paths, c) for c in sorted(project.sources)}
    text = llm.transcript(project, words)
    prompt = llm.load_prompt("summary")
    key = hash_of(text, prompt.body, prompt.meta, notes or "", project.hint or "")
    r = Report("summarize")
    r.step(f"{project.slug}  ({root})")
    done = state.load(paths)["stages"].get("summarize") or {}
    if not ns.force and done.get("inputs") == key and paths.summary.is_file():
        r.ok_(f"{paths.summary.name} is up to date (transcript unchanged)")
        r.data = {"summary": str(paths.summary), "cached": True}
        r.next = "write cuts.yaml  (or: vedit propose-cuts)"
        return r
    clips = {c: (ws[-1]["t1"] if ws else 0.0) for c, ws in words.items()}
    res = llm.ask(
        prompt,
        text,
        vars={"context": llm.context(project, notes)},
        model=ns.model,
        log=paths.logs / "llm.jsonl",
        check=checker(clips),
    )
    value = res.values[0]
    _write(paths.summary, render(value, project.slug, llm.MODELS[res.models[0]][1]))
    state.record_stage(paths, "summarize", key, [paths.summary])
    n = {k: len(value[k]) for k in ("chapters", "visual_moments", "asr_errors", "terms")}
    r.ok_(
        f"{paths.summary.name}: {n['chapters']} chapters, {n['visual_moments']} visual moments, "
        f"{n['asr_errors']} likely ASR errors, {n['terms']} terms"
    )
    report_usage(r, res)
    r.data = {"summary": str(paths.summary), "cached": False, **n, **usage(res)}
    r.next = "write cuts.yaml  (or: vedit propose-cuts)"
    return r
