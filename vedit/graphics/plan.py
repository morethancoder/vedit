"""The layout plan: every resolved cue gets its final window and placement (T build.py `main`, first half).

Order matters and is T's: full-frame scenes first (chapters, doodles, screens) with their crossfades; then the
breaks (joins, layout switches, scene edges); then each A-roll graphic is fitted into one shot and placed.
Compose renders the plan; the plan never renders anything, so it is cheap to print (`vedit build --plan`).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from vedit.graphics import place
from vedit.graphics.big import big_layout, text_em
from vedit.graphics.pages import kinetic_times
from vedit.report import VeditError

KINETIC_PX = 92  # base kinetic line size (T); the measured width keeps the face check honest


LOGO_PX = 72  # label logo (60) + its gap


def label_size(title: str, kicker: str, sub: str, adv: dict, mono: bool = False) -> tuple[int, int]:
    """Measured (width, height) of a label: widest of title 58 px, kicker 27 px, sub 28 px, plus the logo."""
    em = (lambda t: len(t) * 0.6) if mono else (lambda t: _em(t, adv))
    widest = max(em(title) * 58, em(kicker) * 27, em(sub or "") * 28)
    return round(min(900, widest + LOGO_PX)), (220 if sub else 170)


def chip_size(code: str, label: str, adv: dict) -> tuple[int, int]:
    """Measured (width, height) of a chip: its code (40 px Arabic, 36 px mono at 0.6 em/char) or its label."""
    rtl = bool(re.search(r"[\u0600-\u06ff]", code))
    code_w = (_em(code, adv) * 40 if rtl else len(code) * 0.6 * 36) + 60  # prompt + cursor
    return round(max(code_w, _em(label, adv) * 27 + 36)), 140


def _em(text: str, adv: dict) -> float:
    return text_em(text, adv, 0.0)


@dataclass
class Placement:
    cue: object  # vedit.graphics.cues.Cue
    start: float
    dur: float
    track: int  # HyperFrames track index (T: 1 sided graphics, 2 big words, 6 full-frame)
    side: str = ""
    theme: str = "dark"
    blur: bool = False
    cam: bool = True
    face_hit: float = 0.0
    big: dict = field(default_factory=dict)
    width: int = 0  # kinetic text column (px)
    notes: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return self.cue.id

    @property
    def end(self) -> float:
        return self.start + self.dur

    def note(self) -> str:
        bits = list(self.notes)
        if self.side:
            bits.append(f"{self.side} {self.theme}" + (" blur" if self.blur else ""))
        if self.big:
            b = self.big
            bits.append(
                f"{b['side']} of head, {b['fs']}px, {int(b['tuck'] * 100)}% tucked, drift {b['drift']}px"
            )
        return "; ".join(bits)


@dataclass
class Plan:
    items: list[Placement]
    zooms: list[tuple[float, float, float, float]]
    focus: list[tuple[float, float]]  # merged full-frame windows: the A-roll blurs and dims under them
    breaks: list[float]
    total: float

    def problems(self) -> list[str]:
        out = []
        for p in self.items:
            out += [f"{p.id}: {x}" for x in p.cue.problems]
            if p.face_hit > 0:
                out.append(f"{p.id}: touches the face in {p.face_hit:.0%} of samples")
            if p.cue.type == "kinetic":
                late = kinetic_times(p, len([w for w in str(p.cue.fields["words"]).split(" ") if w]))[1]
                if late:
                    out.append(f"{p.id}: {late} words squeezed before the exit")
            if p.dur < 1.0:
                out.append(f"{p.id}: only {p.dur:.1f}s on screen after fitting into its shot")
        return out


def _merge(wins: list[tuple[float, float]], gap: float = 0.05) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for s, e in sorted(wins):
        if out and s - out[-1][1] < gap:
            out[-1] = (out[-1][0], max(out[-1][1], e))
        else:
            out.append((s, e))
    return out


def _custom(c, start: float, dur: float, track, zooms, notes: list[str]) -> Placement:
    """A custom graphic draws in its `box` (default: the whole frame) and is checked against the face track
    unless it says `face: ignore`."""
    face = str(c.fields.get("face") or "check")
    if face not in ("check", "ignore"):
        raise VeditError(
            f"{c.id}: face must be `ignore` (or left out), got {face!r}", next="vedit guide cue-custom"
        )
    box = c.fields.get("box") or [0, 0, place.W, place.H]
    hit = 0.0
    if face == "check":
        hit = round(place.hits_face(place.rect(box), start, start + dur, track, zooms), 3)
    else:
        notes.append("face check skipped (face: ignore)")
    return Placement(c, start, dur, 6, face_hit=hit, notes=notes)


def build_plan(cues, edl, track, lum, adv: dict, big_params: dict | None = None) -> Plan:
    """cues: resolved Cue list (cues.yaml + chapters). track: FaceTrack. lum: place.Lum (or a stand-in)."""
    zooms = place.zoom_plan(edl, track)
    wins = {c.id: [round(c.start, 3), round(max(0.0, c.end - c.start), 3)] for c in cues}
    scenes = [c.id for c in cues if c.type in place.FULL_FRAME]
    fade_notes = place.crossfade_scenes(wins, scenes)
    edges = [wins[c][0] for c in scenes] + [wins[c][0] + wins[c][1] for c in scenes]
    breaks = sorted(set(edl.joins() + place.layout_switches(track, edl.total) + edges))

    items = []
    for c in cues:
        start, dur = wins[c.id]
        notes = [n for n in fade_notes if n.startswith(c.id + " ")]
        if c.type in place.IN_SHOT:
            s0, d0 = start, dur
            start, dur = place.fit_in_shot(start, dur, breaks)
            if (s0, d0) != (start, dur):
                notes.append(f"fitted to its shot: {d0:.1f}s -> {dur:.1f}s")
        if c.type in place.SIDED:
            center = bool(c.fields.get("center"))
            width = height = None
            if c.type == "kinetic":
                width = text_em(str(c.fields["words"]), adv, 0.0) * KINETIC_PX
            elif c.type == "label":
                width, height = label_size(
                    str(c.fields.get("title", "")),
                    str(c.fields.get("kicker", "")),
                    str(c.fields.get("sub") or ""),
                    adv,
                    bool(c.fields.get("mono")),
                )
            elif c.type == "chip":
                width, height = chip_size(str(c.fields.get("code", "")), str(c.fields.get("label", "")), adv)
            pl = place.place_sided(
                c.type, start, start + dur, track, zooms, lum, center=center, width=width, height=height
            )
            items.append(
                Placement(
                    c, start, dur, 1, pl.side, pl.theme, pl.blur, pl.cam, pl.face_hit, notes=notes + pl.notes
                )
            )
            items[-1].width = pl.width
        elif c.type == "big-number":
            # zooms=[]: the host sits inside the scaled #cam, so the punch-in already scales the word with the
            # picture; placing it from zoomed boxes would zoom it twice
            lay = big_layout(start, dur, str(c.fields["word"]), track, [], adv, big_params)
            items.append(Placement(c, start, dur, 2, big=lay, notes=notes))
        elif c.type in place.FULL_FRAME:
            items.append(Placement(c, start, dur, 6, cam=False, notes=notes))
        elif c.type == "custom":
            items.append(_custom(c, start, dur, track, zooms, notes))
        else:  # plug: over the running A-roll, placed by its own template
            items.append(Placement(c, start, dur, 6, notes=notes))
    items.sort(key=lambda p: p.start)
    focus = _merge([(p.start, p.end) for p in items if p.cue.type in place.FULL_FRAME])
    return Plan(items, zooms, focus, breaks, edl.total)
