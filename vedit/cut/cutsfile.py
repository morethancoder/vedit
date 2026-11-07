"""cuts.yaml: strict loading and resolving each cut to a source range through the words model."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from vedit.report import VeditError
from vedit.words import find, norm, parse_near
from vedit.words.model import WINDOW

FILLERS = re.compile(r"^(ا{2,}|ام+|اه+|um|uh|uhm|erm|ah)$")  # T cuts.py; يعني is cut by explicit `say:`

KEYS = {"pauses", "fillers", "cuts", "keep", "pins", "chapters", "end"}
CUT_KEYS = {"near", "say", "from", "to", "why", "window", "pick"}
PIN_KEYS = {"near", "in", "out"}
KEEP_KEYS = {"near", "say"}
CHAPTER_KEYS = {"near", "title", "kicker", "logo"}
PAUSE_KEYS = {"max", "keep"}
ENDS = ("last-word",)


class CutsError(VeditError):
    pass


@dataclass
class Cut:
    near: str
    say: str | None = None
    from_: str | None = None
    to: str | None = None
    why: str = ""
    window: float | None = None
    pick: str | int | None = None  # first | last | 1-based n among in-window matches


@dataclass
class Pin:
    near: str
    in_: float
    out: float


@dataclass
class Keep:
    near: str
    say: str


@dataclass
class Chapter:
    near: str
    title: str
    kicker: str | None = None
    logo: str | None = None


@dataclass
class CutsFile:
    cuts: list[Cut] = field(default_factory=list)
    keep: list[Keep] = field(default_factory=list)
    pins: list[Pin] = field(default_factory=list)
    chapters: list[Chapter] = field(default_factory=list)
    fillers: bool = True
    pauses: dict = field(default_factory=lambda: {"max": 0.5, "keep": 0.3})
    end: str | None = None


@dataclass
class WordCut:
    clip: str
    kind: str  # "phrase" | "filler" | "pin"
    label: str
    why: str
    i0: int | None  # first word index; None for a pin-only cut
    i1: int | None  # last word index, inclusive
    w0: float  # source seconds where the cut starts
    w1: float  # t0 of the word after the span (clip duration if none); a pin-only cut: its `out`
    pin: tuple[float, float] | None = None
    near: str = ""

    @property
    def key(self) -> str:
        return f"{self.clip}|{self.w0:.2f}|{self.w1:.2f}|{self.label}"


def _suggest(key: str, valid) -> str:
    near = difflib.get_close_matches(str(key), sorted(valid), n=1)
    return f" Did you mean '{near[0]}'?" if near else f" Valid keys: {', '.join(sorted(valid))}."


def _keys(f, where: str, d: dict, valid: set) -> None:
    for k in d:
        if k not in valid:
            raise CutsError(f"{f}: unknown key '{k}' in {where}.{_suggest(k, valid)}")


def _list(f, data: dict, key: str) -> list:
    v = data.get(key)
    if v is None:
        return []
    if not isinstance(v, list):
        raise CutsError(
            f"{f}: '{key}' must be a list, got {type(v).__name__}. Write one '- ' item per entry."
        )
    return v


def _item(f, where: str, d, valid: set) -> dict:
    if not isinstance(d, dict):
        raise CutsError(f"{f}: {where} must be a mapping with keys: {', '.join(sorted(valid))}.")
    _keys(f, where, d, valid)
    near = d.get("near")
    if not near:
        raise CutsError(f"{f}: {where} needs 'near' (e.g. near: A 245.0).")
    try:
        parse_near(near)
    except VeditError as e:
        raise CutsError(f"{f}: {where}: {e.message}") from None
    return d


def _num(f, where: str, d: dict, key: str, required: bool = False) -> float | None:
    v = d.get(key)
    if v is None:
        if required:
            raise CutsError(f"{f}: {where} needs '{key}' (seconds).")
        return None
    if isinstance(v, bool) or not isinstance(v, int | float):
        raise CutsError(f"{f}: {where}: '{key}' must be a number of seconds, got {v!r}.")
    return float(v)


def _text(f, where: str, d: dict, key: str) -> str | None:
    v = d.get(key)
    if v is None:
        return None
    if not isinstance(v, str) or not v.strip():
        raise CutsError(f"{f}: {where}: '{key}' must be non-empty text, got {v!r}.")
    return v


def load(path) -> CutsFile:
    f = Path(path)
    if not f.exists():
        raise CutsError(f"no cuts file at {f}", next="write cuts.yaml (vedit guide cuts)")
    try:
        data = yaml.safe_load(f.read_text()) or {}
    except yaml.YAMLError as e:
        raise CutsError(f"{f}: not valid YAML: {e}") from None
    if not isinstance(data, dict):
        raise CutsError(f"{f}: must be a mapping with keys: {', '.join(sorted(KEYS))}.")
    _keys(f, "the top level", data, KEYS)
    cf = CutsFile()
    fl = data.get("fillers", True)
    if not isinstance(fl, bool):
        raise CutsError(f"{f}: 'fillers' must be true or false, got {fl!r}.")
    cf.fillers = fl
    p = data.get("pauses")
    if p is not None:
        if not isinstance(p, dict):
            raise CutsError(f"{f}: 'pauses' must be a mapping like {{ max: 0.5, keep: 0.3 }}.")
        _keys(f, "pauses", p, PAUSE_KEYS)
        for k in p:
            cf.pauses[k] = _num(f, "pauses", p, k)
    end = data.get("end")
    if end is not None and end not in ENDS:
        raise CutsError(f"{f}: 'end' must be one of: {', '.join(ENDS)}; got {end!r}.")
    cf.end = end
    for n, d in enumerate(_list(f, data, "cuts")):
        w = f"cuts[{n}]"
        _item(f, w, d, CUT_KEYS)
        c = Cut(d["near"], _text(f, w, d, "say"), _text(f, w, d, "from"), _text(f, w, d, "to"))
        c.why = d.get("why") or ""
        c.window = _num(f, w, d, "window")
        if c.window is not None and c.window <= 0:
            raise CutsError(f"{f}: {w}: 'window' must be above 0 seconds.")
        c.pick = d.get("pick")
        if (
            c.pick is not None
            and c.pick not in ("first", "last")
            and not (isinstance(c.pick, int) and not isinstance(c.pick, bool) and c.pick >= 1)
        ):
            raise CutsError(f"{f}: {w}: 'pick' must be first, last or a number from 1, got {c.pick!r}.")
        if c.say and (c.from_ or c.to):
            raise CutsError(f"{f}: {w} has both 'say' and 'from'/'to'. Use one form.")
        if not c.say and not (c.from_ and c.to):
            raise CutsError(f"{f}: {w} needs 'say', or both 'from' and 'to'.")
        cf.cuts.append(c)
    for n, d in enumerate(_list(f, data, "keep")):
        w = f"keep[{n}]"
        _item(f, w, d, KEEP_KEYS)
        if not _text(f, w, d, "say"):
            raise CutsError(f"{f}: {w} needs 'say' (the word to never cut as a filler).")
        cf.keep.append(Keep(d["near"], d["say"]))
    for n, d in enumerate(_list(f, data, "pins")):
        w = f"pins[{n}]"
        _item(f, w, d, PIN_KEYS)
        a, b = _num(f, w, d, "in", True), _num(f, w, d, "out", True)
        if b <= a:
            raise CutsError(f"{f}: {w}: 'out' ({b}) must come after 'in' ({a}).")
        cf.pins.append(Pin(d["near"], a, b))
    for n, d in enumerate(_list(f, data, "chapters")):
        w = f"chapters[{n}]"
        _item(f, w, d, CHAPTER_KEYS)
        title = _text(f, w, d, "title")
        if not title:
            raise CutsError(f"{f}: {w} needs 'title'.")
        cf.chapters.append(Chapter(d["near"], title, _text(f, w, d, "kicker"), _text(f, w, d, "logo")))
    return cf


def _problem(index, near: str, text: str, e: VeditError, section: str = "cuts") -> dict:
    return {
        "section": section,
        "cut": index,
        "near": near,
        "text": text,
        "error": e.message,
        "candidates": getattr(e, "candidates", []),
    }


def _end(words: list[dict], i1: int, dur: float | None) -> float:
    """t0 of the next word, never before the span's own last word ends (ASR times can run backwards)."""
    if i1 + 1 < len(words):
        return max(words[i1 + 1]["t0"], words[i1]["t1"])
    return dur if dur is not None else words[i1]["t1"]


def _resolve_cut(c: Cut, words_by_clip: dict, durations: dict) -> tuple[str, int, int, str]:
    win = c.window or WINDOW
    if c.say:
        s = find(words_by_clip, c.say, c.near, win, c.pick)
        return s.clip, s.i0, s.i1, c.say
    a = find(words_by_clip, c.from_, c.near, win, c.pick)
    # `to` is looked for among the words after `from`, near where `from` ends
    rest = {a.clip: words_by_clip[a.clip][a.i1 + 1 :]}
    b = find(rest, c.to, f"{a.clip} {a.t1}", win)
    return a.clip, a.i0, a.i1 + 1 + b.i1, f"{c.from_} … {c.to}"


def resolve(cf: CutsFile, words_by_clip: dict, durations: dict) -> tuple[list[WordCut], list[dict]]:
    """Each cut -> a source range. Unresolved cuts come back as problems, never silently skipped."""
    out: list[WordCut] = []
    problems: list[dict] = []
    for n, c in enumerate(cf.cuts):
        try:
            clip, i0, i1, label = _resolve_cut(c, words_by_clip, durations)
        except VeditError as e:
            problems.append(_problem(n, c.near, c.say or f"{c.from_} … {c.to}", e))
            continue
        w = words_by_clip[clip]
        out.append(
            WordCut(
                clip,
                "phrase",
                label,
                c.why,
                i0,
                i1,
                w[i0]["t0"],
                _end(w, i1, durations.get(clip)),
                None,
                c.near,
            )
        )

    if cf.fillers:
        kept: set[tuple[str, int]] = set()
        for n, k in enumerate(cf.keep):
            try:
                s = find(words_by_clip, k.say, k.near)
            except VeditError as e:
                problems.append(_problem(n, k.near, k.say, e, "keep"))
                continue
            kept.update((s.clip, i) for i in range(s.i0, s.i1 + 1))
        for clip, w in words_by_clip.items():
            for i, x in enumerate(w):
                if FILLERS.match(norm(x["w"])) and (clip, i) not in kept:
                    out.append(
                        WordCut(
                            clip,
                            "filler",
                            x["w"],
                            "filler",
                            i,
                            i,
                            x["t0"],
                            _end(w, i, durations.get(clip)),
                            None,
                            f"{clip} {x['t0']}",
                        )
                    )

    for n, p in enumerate(cf.pins):
        clip, t = parse_near(p.near)
        hits = [
            c
            for c in out
            if c.kind != "pin" and c.clip == clip and c.w0 < p.out and p.in_ < c.w1 and c.pin is None
        ]
        if hits:
            min(hits, key=lambda c: abs(c.w0 - t)).pin = (p.in_, p.out)
        elif clip not in words_by_clip:
            problems.append(
                _problem(n, p.near, f"{p.in_}-{p.out}", VeditError(f"pin: no words for clip {clip}"), "pins")
            )
        else:
            out.append(
                WordCut(
                    clip,
                    "pin",
                    f"{p.in_:g}-{p.out:g}",
                    "pin",
                    None,
                    None,
                    p.in_,
                    p.out,
                    (p.in_, p.out),
                    p.near,
                )
            )
    out.sort(key=lambda c: (c.clip, c.w0))
    return out, problems
