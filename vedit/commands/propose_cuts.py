"""vedit propose-cuts: cuts.proposed.yaml, a first-draft cut list for review. Never touches cuts.yaml."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from vedit import llm, state
from vedit.commands.llm import report_usage, usage
from vedit.commands.transcribe import _find, _write, lines
from vedit.report import Report, VeditError
from vedit.run import hash_of
from vedit.words import AmbiguousMatch, NoMatch, Span, find, norm, parse_near, tokens
from vedit.words import load as load_words

EPILOG = "example: vedit propose-cuts --model sonnet"
OUT = "cuts.proposed.yaml"
MAX_MISSES = 0.25  # more unmatched cuts than this and the reply is retried (the model is not copying words)
LONG_WORDS, LONG_SECS = 9, 4.0  # a cut this long may be story content, not cleanup
CONTEXT_WORDS = 5

NEGATION_TEXT = "ما مو مش ماكو ماكان لا ليس لم لن مب not no never dont don't cant can't"
NUMBER_TEXT = (
    "صفر واحد وحده اثنين ثنين ثلاث ثلاثة تلاث اربع اربعة خمس خمسة ست ستة سبع سبعة ثمان ثمانية تسع تسعة "
    "عشر عشرة عشرين ثلاثين اربعين خمسين ستين سبعين ثمانين تسعين مية ميه مئة مائة مئتين ميتين "
    "الف الاف آلاف مليون ملايين مليار نص ربع اثنعش اطنعش"
)
NEGATIONS = {norm(w) for w in NEGATION_TEXT.split()}
NUMBER_WORDS = {norm(w) for w in NUMBER_TEXT.split()}
DIGIT_RE = re.compile(r"[0-9٠-٩۰-۹]")
LATIN_RE = re.compile(r"[A-Za-z]{2,}")


def add_args(sp) -> None:
    sp.add_argument("--notes", metavar="FILE", help="the speaker's outline, given to the model as context")
    sp.add_argument(
        "--model", default="auto", choices=["auto", *llm.MODELS], metavar="M", help="force a model"
    )
    sp.add_argument("--force", action="store_true", help="redo even when the transcript has not changed")
    sp.epilog = EPILOG


def _is_number(tok: str) -> bool:
    if DIGIT_RE.search(tok):
        return True
    t = tok[1:] if tok[:1] in ("و", "ب") and len(tok) > 3 else tok  # و/ب + number word
    return tok in NUMBER_WORDS or t in NUMBER_WORDS


BOUND_AFTER = {
    norm(w) for w in ["لله", "الله"]
}  # a cut ending before these leaves "الحمد" / "إن شاء" torn off


def risks(words: list[dict], names: set[str], before: str = "", after: str = "") -> list[str]:
    """Why a cut deserves a look first: it removes a number, a name, a negation or a long stretch, or its join
    puts a negation where there was none, or tears a fixed phrase."""
    toks = [norm(w["w"]) for w in words]
    out = []
    if norm(after) in NEGATIONS and toks[-1] not in NEGATIONS:
        out.append(f"join: negation {after} now follows {before or 'the start'} (meaning flip?)")
    if norm(after) in BOUND_AFTER:
        out.append(f"join: leaves {after} torn from its phrase")
    if norm(before) in {norm("أنا"), norm("آني")}:
        out.append(f"cut right after {before}: a name?")
    neg = [w["w"] for w, t in zip(words, toks, strict=True) if t in NEGATIONS]
    if neg:
        out.append(f"negation {' '.join(neg)}")
    nums = [w["w"] for w, t in zip(words, toks, strict=True) if _is_number(t)]
    if nums:
        out.append(f"number {' '.join(nums)}")
    nm = [w["w"] for w, t in zip(words, toks, strict=True) if t in names or LATIN_RE.search(w["w"])]
    if nm:
        out.append(f"name {' '.join(nm)}")
    secs = words[-1]["t1"] - words[0]["t0"]
    if len(words) >= LONG_WORDS or secs >= LONG_SECS:
        out.append(f"long: {len(words)} words, {secs:.1f}s (story content?)")
    return out


def line_starts(ws: list[dict]) -> dict[str, int]:
    """`12.6` -> index of the first word of the transcript line the model saw as `[A 12.6]`."""
    out, i = {}, 0
    for g in lines(ws, maxw=llm.LINE_WORDS):
        out.setdefault(f"{g[0]['t0']:.1f}", i)
        i += len(g)
    return out


def _in_lines(ws: list[dict], starts: dict[str, int], t: float, say: str) -> Span | None:
    """The first match of `say` inside the line that starts at `t` or the line after it (the prompt's rule)."""
    i0 = starts.get(f"{t:.1f}")
    if i0 is None:
        return None
    later = sorted(i for i in starts.values() if i > i0)
    end = later[1] if len(later) > 1 else len(ws)
    want = tokens(say)
    keys = [norm(w["w"]) for w in ws[i0:end]]
    for k in range(len(keys) - len(want) + 1):
        if want and keys[k : k + len(want)] == want:
            a, b = i0 + k, i0 + k + len(want) - 1
            return Span("", a, b, ws[a]["t0"], ws[b]["t1"], " ".join(w["w"] for w in ws[a : b + 1]))
    return None


def match(cuts: list[dict], words_by_clip: dict[str, list[dict]]) -> tuple[list[dict], list[dict]]:
    """Locate each proposed cut by its words: inside the line it names, else near its time.

    Returns (found, missed); a cut overlapping an earlier one is dropped.
    """
    starts = {c: line_starts(ws) for c, ws in words_by_clip.items()}
    found, missed = [], []
    for c in cuts:
        near = str(c["near"]).strip("[] ")
        if len(words_by_clip) == 1 and not re.match(r"^[A-Za-z]", near):
            near = f"{next(iter(words_by_clip))} {near}"
        try:
            clip, t = parse_near(near)
            span = None
            if clip in words_by_clip:
                span = _in_lines(words_by_clip[clip], starts[clip], t, c["say"])
            if span is not None:
                span.clip = clip
            else:
                span = find(words_by_clip, c["say"], near)
        except (NoMatch, AmbiguousMatch, VeditError) as e:
            missed.append({**c, "error": e.message.splitlines()[0]})
            continue
        found.append({**c, "span": span})
    found.sort(key=lambda c: (c["span"].clip, c["span"].i0))
    kept, last = [], {}
    for c in found:
        s = c["span"]
        if s.i0 <= last.get(s.clip, -1):
            missed.append({**{k: v for k, v in c.items() if k != "span"}, "error": "overlaps an earlier cut"})
            continue
        last[s.clip] = s.i1
        kept.append(c)
    return kept, missed


def _ambiguous(words_by_clip: dict, say: str, near: str) -> bool:
    """True when `say` near `near` matches twice within a second (a stutter): `vedit cut` asks which one."""
    try:
        find(words_by_clip, say, near)
    except AmbiguousMatch:
        return True
    except VeditError:
        pass
    return False


def checker(words_by_clip: dict[str, list[dict]]):
    def check(value: dict, _text: str) -> None:
        if not value["cuts"]:
            return
        _, missed = match(value["cuts"], words_by_clip)
        if len(missed) > MAX_MISSES * len(value["cuts"]):
            ex = "; ".join(f"{m['near']} {m['say']!r}: {m['error']}" for m in missed[:3])
            raise llm.Invalid(f"{len(missed)}/{len(value['cuts'])} cuts do not match the transcript ({ex})")

    return check


def _q(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)  # a JSON string is a valid YAML double-quoted scalar


def render(cuts: list[dict], words_by_clip: dict, model: str, missed: int) -> str:
    risky = [c for c in cuts if c["risky"]]
    safe = [c for c in cuts if not c["risky"]]
    out = [
        f"# {OUT}: first-draft cuts from `vedit propose-cuts` ({model}, {time.strftime('%Y-%m-%d')}).",
        "# Not read by `vedit cut`. Review, then copy the cuts you agree with into cuts.yaml (`vedit guide cuts`).",
        f"# {len(cuts)} cuts; the {len(risky)} risky ones come first (they remove a number, a name, a negation",
        "# or a long stretch): check each by reading the words around it. `# ...` lines show those words.",
    ]
    if missed:
        out.append(f"# {missed} more proposals did not match the transcript and were left out.")
    out.append("cuts:")
    for title, group in (("risky: review these first", risky), ("the rest, in time order", safe)):
        if not group:
            continue
        out.append(f"  # ---- {title} ----")
        for c in group:
            s = c["span"]
            ws = words_by_clip[s.clip]
            before = " ".join(w["w"] for w in ws[max(0, s.i0 - CONTEXT_WORDS) : s.i0])
            after = " ".join(w["w"] for w in ws[s.i1 + 1 : s.i1 + 1 + CONTEXT_WORDS])
            out.append(f"  - near: {s.clip} {s.t0:.1f}")
            out.append(f"    say: {_q(c['say'])}")
            why = _q(c["why"])
            out.append(f"    why: {why}" + (f"  # RISKY: {'; '.join(c['risky'])}" if c["risky"] else ""))
            out.append(f"    # ... {before} [{s.text}] {after} ...")
            if c.get("repeat"):
                out.append("    # REPEAT: these words occur more than once nearby; add pick: first|last|<n>")
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
    prompt = llm.load_prompt("cuts")
    key = hash_of(text, prompt.body, prompt.meta, notes or "", project.hint or "")
    out = root / OUT
    r = Report("propose-cuts")
    r.step(f"{project.slug}  ({root})")
    done = state.load(paths)["stages"].get("propose-cuts") or {}
    if not ns.force and done.get("inputs") == key and out.is_file():
        r.ok_(f"{OUT} is up to date (transcript unchanged)")
        r.data = {"proposed": str(out), "cached": True}
        r.next = f"review {OUT}, then write cuts.yaml"
        return r
    res = llm.ask(
        prompt,
        text,
        vars={"context": llm.context(project, notes)},
        model=ns.model,
        log=paths.logs / "llm.jsonl",
        check=checker(words),
    )
    raw = [c for v in res.values for c in v["cuts"]]
    found, missed = match(raw, words)
    names = {norm(t) for t in re.split(r"[,\s]+", project.hint or "") if t}
    for c in found:
        s = c["span"]
        ws = words[s.clip]
        before = ws[s.i0 - 1]["w"] if s.i0 > 0 else ""
        after = ws[s.i1 + 1]["w"] if s.i1 + 1 < len(ws) else ""
        c["risky"] = risks(ws[s.i0 : s.i1 + 1], names, before, after)
        c["repeat"] = _ambiguous(words, c["say"], f"{s.clip} {s.t0:.1f}")
    model = llm.MODELS[res.models[0]][1]
    _write(out, render(found, words, model, len(missed)))
    state.record_stage(paths, "propose-cuts", key, [out])
    n_risky = sum(1 for c in found if c["risky"])
    secs = sum(c["span"].t1 - c["span"].t0 for c in found)
    r.ok_(f"{OUT}: {len(found)} cuts ({secs:.0f}s of words), {n_risky} risky first")
    for m in missed[:5]:
        r.warn(f"left out {m['near']} {m['say']!r}: {m['error']}")
    if len(missed) > 5:
        r.warn(f"... {len(missed) - 5} more left out")
    report_usage(r, res)
    r.data = {
        "proposed": str(out),
        "cached": False,
        "cuts": [
            {
                "near": f"{c['span'].clip} {c['span'].t0:.2f}",
                "say": c["say"],
                "why": c["why"],
                "risky": c["risky"],
            }
            for c in found
        ],
        "missed": missed,
        **usage(res),
    }
    r.next = f"review {OUT}, then write cuts.yaml"
    return r
