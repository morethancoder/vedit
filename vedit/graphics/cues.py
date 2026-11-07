"""cues.yaml: strict loading, validation against the style pack's slots, and word anchors -> program windows.

A cue is anchored to spoken words in source time and mapped through the edl, so a cut change never needs
re-timing. A cue whose anchor words were cut away is kept and reported in `Cue.problems`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from vedit import channel as chan
from vedit.doodles import library as doodle_library
from vedit.graphics import pack as packs
from vedit.graphics.anchors import FORWARD, closest, first_after, spans, spoken_onsets, words_kept
from vedit.report import VeditError
from vedit.run import hash_of
from vedit.words import Edl, Span, find

DEFAULT_LEN = {"label": 6.0, "chip": 8.0, "big-number": 5.0, "screen": 8.0, "plug": 18.0}
KINETIC_TAIL = 1.2  # seconds after the last shown word
DOODLE_TAIL = 2.5  # seconds after the last beat
KINETIC_STEP = 0.25  # onset gap when the transcript has fewer words than the line shows
LEAD = 1.0  # beats and words slots may be spoken this long before the anchor
REACH = 5.0  # ...and this long after the cue's source span
CHAPTER_LEAD, CHAPTER_TAIL = (
    0.5,
    0.9,
)  # T: a chapter card starts 0.5 s before its hold and ends 0.9 s after it
TOP_KEYS = {"style", "cues"}
FIX = "fix cues.yaml (vedit guide cues; one page per type: vedit guide cue-<type>)"


@dataclass
class Cue:
    id: str
    type: str
    style: str
    fields: dict
    clip: str = ""
    src: float = 0.0  # source t0 of the anchor
    start: float = 0.0  # program seconds
    end: float = 0.0
    spoken: list[float] = field(default_factory=list)  # program onset of each transcript word from the anchor
    beats: dict[str, float] = field(default_factory=dict)  # doodle element -> program time
    times: dict[str, float] = field(default_factory=dict)  # each `kind: words` slot -> program time
    problems: list[str] = field(default_factory=list)
    key: str = ""


def custom_logos(paths, channel: str | None = None) -> dict[str, Path]:
    """Your logos, by name: `<config>/logos/`, then the channel's `logos/`, then the project's `custom/logos/`
    (later wins; all win over the style pack's)."""
    dirs = [chan.config_dir() / "logos"]
    if channel:
        dirs.append(chan.config_dir() / "channels" / channel / "logos")
    dirs.append(Path(paths.custom) / "logos")
    out = {}
    for d in dirs:
        if d.is_dir():
            for f in sorted(d.iterdir()):
                if f.suffix in (".svg", ".png"):
                    out[f.stem] = f
    return out


class _Packs:
    def __init__(self, roots):
        self.roots, self.cache = roots, {}

    def get(self, name: str):
        if name not in self.cache:
            self.cache[name] = packs.load(name, self.roots)
        return self.cache[name]


def _anchor(words_by_clip: dict, c: dict) -> Span:
    at = c["at"]
    if c.get("near") is not None:
        return find(words_by_clip, at, str(c["near"]), float(c.get("window", 6.0)), c.get("pick"))
    hits = [s for clip, ws in words_by_clip.items() for s in spans(ws, at, clip)]
    if len(hits) == 1:
        return hits[0]
    if not hits:
        raise VeditError(
            f"no match for {at!r} in any clip", next="fix the words, or add `near: <clip> <seconds>`"
        )
    where = ", ".join(f"{s.clip} {s.t0:.1f}" for s in hits[:6])
    raise VeditError(f"{at!r} matches {len(hits)} places ({where})", next="add `near: <clip> <seconds>`")


def _src_of(edl: Edl, t: float, clip: str, fallback: float) -> float:
    c, s = edl.src(max(t - 0.001, 0.0))
    return s if c == clip else fallback


def _after(
    words: list[dict], phrase: str, clip: str, t_from: float, t_to: float, what: str, probs: list[str]
):
    s = first_after(words, phrase, clip, t_from, t_to)
    if s is None:
        probs.append(
            f"{what}: {phrase!r} not spoken between {t_from:.1f}s and {t_to:.1f}s of {clip}. Closest:\n"
            + closest(words, phrase, clip, t_from)
        )
    return s


def _resolve(c: dict, cid: str, edl: Edl, wbc: dict) -> Cue:
    """Anchor, end, beats and word slots of one cue (fields/style are filled by the caller)."""
    cue = Cue(cid, c["type"], "", {})
    sp = _anchor(wbc, c)
    words = wbc[sp.clip]
    cue.clip, cue.src, cue.start = sp.clip, sp.t0, edl.g(sp.clip, sp.t0)
    if not words_kept(edl, sp.clip, words, sp.i0, sp.i1):
        cue.problems.append(
            f"anchor words {sp.text!r} ({sp.clip} {sp.t0:.2f}s) were cut away from the program"
        )
    typ = c["type"]
    limit = sp.t0 + FORWARD
    end = src_end = None
    if "until" in c:
        u = c["until"]
        if u == "end":
            end = edl.total
        elif c.get("until_near") is not None:
            us = find(wbc, str(u), str(c["until_near"]))
            end, src_end = edl.g(us.clip, us.t1), us.t1
        else:
            us = first_after(words, str(u), sp.clip, sp.t0, limit)
            if us is None:
                raise VeditError(
                    f"until {u!r} is not spoken within {FORWARD:g}s after {sp.clip} {sp.t0:.1f}s",
                    next="quote the words that end it, or use `for: <seconds>`",
                )
            end, src_end = edl.g(sp.clip, us.t1), us.t1
    elif "for" in c:
        end = cue.start + float(c["for"])
    elif typ == "custom":
        raise VeditError("a custom cue needs `for: <seconds>`", next="add `for:` to it")
    if end is not None and src_end is None:
        src_end = _src_of(edl, end, sp.clip, limit)
    reach = (src_end if src_end is not None else limit) + REACH
    cue.spoken = spoken_onsets(edl, sp.clip, words, sp.i0, reach)
    # doodle beats and `kind: words` slots: first match from anchor-1s within the cue's source span + 5s
    beats = c.get("beats") if isinstance(c.get("beats"), dict) else {}
    for el, phrase in beats.items():
        s = _after(words, str(phrase), sp.clip, sp.t0 - LEAD, reach, f"beat {el!r}", cue.problems)
        if s is not None:
            cue.beats[el] = edl.g(sp.clip, s.t0)
    for name in c.get("_words_slots", []):
        s = _after(words, str(c[name]), sp.clip, sp.t0 - LEAD, reach, f"{name!r}", cue.problems)
        if s is not None:
            cue.times[name] = edl.g(sp.clip, s.t0)
    if end is None:
        end = _default_end(c, cue)
    cue.end = round(end, 3)
    if cue.end <= cue.start:
        cue.problems.append(f"ends at {cue.end:.2f}s, not after its start {cue.start:.2f}s")
    cue.spoken = [t for t in cue.spoken if t <= cue.end]
    return cue


def _default_end(c: dict, cue: Cue) -> float:
    typ = c["type"]
    if typ == "kinetic":
        n = len(str(c.get("words", "")).split())
        sp = cue.spoken
        if not sp or n == 0:
            return cue.start + KINETIC_TAIL + 1.0
        last = sp[n - 1] if n <= len(sp) else sp[-1] + KINETIC_STEP * (n - len(sp))
        return last + KINETIC_TAIL
    if typ == "doodle":
        return (max(cue.beats.values()) if cue.beats else cue.start) + DOODLE_TAIL
    return cue.start + DEFAULT_LEN.get(typ, 6.0)


def _words_slots(tpl) -> list[str]:
    return [n for n, s in tpl.slots.items() if s.kind == "words"]


def _key(cue: Cue, pk, tpl, logos: dict, root: Path) -> str:
    parts: list = [
        cue.type,
        cue.style,
        cue.fields,
        cue.clip,
        round(cue.start, 3),
        round(cue.end, 3),
        cue.beats,
        cue.times,
        tpl.path,
        pk.file("pack.yaml"),
    ]
    if cue.type == "kinetic":
        parts.append([round(t, 3) for t in cue.spoken])
    for n, s in tpl.slots.items():
        v = cue.fields.get(n)
        if v is None:
            continue
        if s.kind == "logo" and str(v) in logos:
            parts.append(logos[str(v)])
        elif s.kind == "file" and _inside(root, v) and (root / str(v)).is_file():
            parts.append(root / str(v))
    return hash_of(*[p for p in parts if p is not None])


def _inside(root: Path, rel) -> bool:
    """A cue's `file:` stays inside the project folder (no `..`, no absolute path out)."""
    return (Path(root) / str(rel)).resolve().is_relative_to(Path(root).resolve())


ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
RESERVED_IDS = {"main", "root", "cam", "fade", "program"}
RESERVED_PREFIXES = ("sfx-", "mt-", "chapter-")
COLOR_RE = re.compile(
    r"^(#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})"
    r"|(?:rgb|rgba|hsl|hsla)\(\s*[0-9.,%\s/-]+\)"
    r"|[A-Za-z]+)$"
)


def check_id(cid: str) -> str:
    """Why a cue id is not allowed (it reaches file names, HTML ids and JS strings), or ''."""
    if not ID_RE.match(cid):
        return f"id {cid!r} must be lowercase letters, digits and dashes, starting with a letter or digit (e.g. `k-pressure`)"
    if cid in RESERVED_IDS or cid.startswith(RESERVED_PREFIXES):
        return f"id {cid!r} is reserved (main, root, cam, fade, program, sfx-*, mt-*, chapter-*): pick another id"
    return ""


def _read(f: Path) -> dict:
    if not f.exists():
        return {}
    try:
        data = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        raise VeditError(f"{f}: not valid YAML ({e})", next=FIX) from e
    if not isinstance(data, dict):
        raise VeditError(f"{f}: top level must be a mapping with `cues:`", next=FIX)
    for k in data:
        if k not in TOP_KEYS:
            raise VeditError(f"{f}: unknown top-level key {k!r} (use: style, cues)", next=FIX)
    return data


def file_style(paths) -> str | None:
    """cues.yaml's top-level `style:` (None when there is no file or it sets none; errors surface in load)."""
    try:
        return _read(Path(paths.cues)).get("style") or None
    except VeditError:
        return None


def load(project, paths, edl: Edl, words_by_clip: dict, roots: list[Path] | None = None) -> list[Cue]:
    """Cues of cues.yaml resolved to program windows. Raises one VeditError listing every invalid cue."""
    data = _read(Path(paths.cues))
    raw = data.get("cues") or []
    if not isinstance(raw, list):
        raise VeditError("cues.yaml: `cues:` must be a list", next=FIX)
    pool = _Packs(roots)
    file_style = chan.style_choice(project, data.get("style"))[0]
    clogos = custom_logos(paths, getattr(project, "channel", None))
    root = Path(paths.root)
    out, errs, counts, seen = [], [], {}, set()
    for n, c in enumerate(raw):
        typ = c.get("type") if isinstance(c, dict) else None
        counts[typ] = counts.get(typ, 0) + 1
        cid = str(c.get("id")) if isinstance(c, dict) and c.get("id") else f"{typ}-{counts[typ]}"
        where = f"cues[{n}] {cid}"
        if not isinstance(c, dict) or not typ or "at" not in c:
            errs.append(f"{where}: needs `type` and `at`")
            continue
        if isinstance(c, dict) and c.get("id"):
            bad_id = check_id(cid)
            if bad_id:
                errs.append(f"{where}: {bad_id}")
                continue
        if cid in seen:
            errs.append(f"{where}: duplicate id {cid!r}")
        seen.add(cid)
        if typ == "chapter":
            errs.append(f"{where}: chapters come from cuts.yaml `chapters:`, not cues.yaml")
            continue
        style = str(c.get("style") or file_style)
        try:
            pk = pool.get(style)
            tpl = pk.template(typ)
        except VeditError as e:
            errs.append(f"{where}: {e}")
            continue
        logos = {**pk.logos(), **clogos}
        fields = {k: v for k, v in c.items() if k not in packs.CUE_KEYS}
        bad = packs.check_fields(tpl, c, where, logos)
        if typ == "doodle":
            bad += doodle_library.check_cue(c, where)  # scene name or inline spec, beat names
        for k, v in fields.items():
            if (
                k in tpl.slots
                and tpl.slots[k].kind == "file"
                and isinstance(v, str)
                and not (_inside(root, v) and (root / v).is_file())
            ):
                bad.append(f"{where}: file {v!r} not found under the project")
        if isinstance(c.get("beats"), dict):
            bad += [
                f"{where}: beat key {k!r} is not text (YAML reads bare no/on/yes as booleans): quote it"
                for k in c["beats"]
                if not isinstance(k, str)
            ]
        if "color" in tpl.slots or "color" in c:
            col = c.get("color")
            if col is not None and not (isinstance(col, str) and COLOR_RE.match(col.strip())):
                bad.append(
                    f"{where}: color {col!r} is not a CSS colour; use #rgb, #rrggbb, #rrggbbaa, "
                    "rgb()/rgba()/hsl() with numbers, a colour word like gold, or `accent` (the style's accent)"
                )
        if "until" in c and "for" in c:
            bad.append(f"{where}: use `until` or `for`, not both")
        if bad:
            errs += bad
            continue
        try:
            cue = _resolve(
                {**c, "_words_slots": [s for s in _words_slots(tpl) if s in c]}, cid, edl, words_by_clip
            )
        except VeditError as e:
            errs.append(f"{where}: {e}" + (f"\n    next: {e.next}" if getattr(e, "next", None) else ""))
            continue
        cue.style, cue.fields = style, fields
        cue.key = _key(cue, pk, tpl, logos, root)
        out.append(cue)
    if errs:
        raise VeditError(f"cues.yaml: {len(errs)} problem(s)\n" + "\n".join(f"  {e}" for e in errs), next=FIX)
    return out


def chapters(cuts_file, edl: Edl, pack=None, logos: dict | None = None, style: str = packs.BASE) -> list[Cue]:
    """One chapter cue per cuts.yaml chapter, paired in order with the edl's holds."""
    holds = edl.holds()
    chs = list(cuts_file.chapters)
    if len(chs) != len(holds):
        raise VeditError(
            f"cuts.yaml has {len(chs)} chapter(s) but the edl has {len(holds)} hold(s)",
            next="one `chapters:` entry per hold, in order; re-run `vedit cut` after editing cuts.yaml",
        )
    pk = pack or packs.load(style)
    tpl = pk.template("chapter")
    logos = logos if logos is not None else pk.logos()
    out, errs = [], []
    for n, (ch, (hs, hl)) in enumerate(zip(chs, holds, strict=True), 1):
        fields = {k: v for k, v in (("title", ch.title), ("kicker", ch.kicker), ("logo", ch.logo)) if v}
        errs += packs.check_fields(tpl, fields, f"chapters[{n - 1}]", logos)
        clip, s = edl.src(hs + 0.001)
        start = max(0.0, hs - CHAPTER_LEAD)
        cue = Cue(
            f"chapter-{n}",
            "chapter",
            pk.name,
            fields,
            clip,
            s,
            round(start, 3),
            round(hs - CHAPTER_LEAD + hl + CHAPTER_TAIL, 3),
        )
        cue.key = hash_of(cue.type, cue.style, fields, cue.start, cue.end, tpl.path, pk.file("pack.yaml"))
        out.append(cue)
    if errs:
        raise VeditError("cuts.yaml chapters: " + "; ".join(errs), next="vedit guide cue-chapter")
    return out
