"""Write the HyperFrames project `.vedit/hf/` from a layout plan (T build.py `host`, `index`, SFX, `chunk_bounds`).

Full-frame path (the overlay spike was not adopted): one root `index.html` plays the program with its sound,
and every graphic is a sub-composition host. Graphics are grouped by layer so an overlay render could slot in
later: `behind` hosts sit inside `#cam` under the person cut-out (big words), `front` hosts above it. What
touches the footage itself (punch-in zooms, the focus blur + dim under full-frame scenes, the end fade) comes
from the plan and the pack's `focus` numbers, never from the type templates.

Incremental: `.vedit/hf/manifest.json` keeps each composition's key (cue key + placement + pack files +
engine); a file whose key did not change is not rendered or rewritten, and a removed cue's file is deleted.
"""

from __future__ import annotations

import filecmp
import itertools
import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from vedit.graphics import pages

GSAP_JS = Path(__file__).resolve().parent.parent / "vendor" / "gsap" / "gsap.min.js"  # pinned: versions.GSAP

FRONT_TRACK, BEHIND_TRACK, SCENE_TRACK, MATTE_TRACK, SFX_TRACK = 1, 2, 6, 3, 7
CHUNK = 150.0  # seconds per 4K render chunk (T render.sh)
BEAT_GAP = 0.3  # beats drawn back to back get one click, not a pile-up (T)


@dataclass
class Graphic:
    id: str
    type: str
    start: float
    dur: float
    layer: str  # "behind" (inside #cam, under the cut-out) | "front"
    track: int
    sounds: list[tuple[str, float]] = field(default_factory=list)  # (kind, program seconds)
    matte: str = ""  # cut-out name (big words)


@dataclass
class Result:
    graphics: list[Graphic]
    sfx: list[tuple]  # (t, length, name, gain, track, n)
    written: list[str]
    reused: list[str]
    removed: list[str]
    chunks: list[float]
    index_changed: bool


def layer_of(p) -> tuple[str, int]:
    if p.cue.type == "big-number":
        return "behind", BEHIND_TRACK
    return "front", (FRONT_TRACK if p.track == 1 else SCENE_TRACK)


SCENE_TRACKS = (SCENE_TRACK, 5, 4)  # tracks 4 and 5 are free: overlapping scenes (a crossfade) alternate


def assign_scene_tracks(graphics: list[Graphic]) -> None:
    """Full-frame hosts go on track 6; one that overlaps an earlier one in time moves to 5 (then 4), so no two
    clips of a track overlap (HyperFrames reads that as an error)."""
    ends = {t: -1.0 for t in SCENE_TRACKS}
    for g in sorted((g for g in graphics if g.track in SCENE_TRACKS), key=lambda g: g.start):
        free = [t for t in SCENE_TRACKS if ends[t] <= g.start + 1e-6]
        g.track = free[0] if free else SCENE_TRACK
        ends[g.track] = g.start + g.dur


# ---- sound ----


def place_sfx(graphics: list[Graphic], pk) -> list[tuple]:
    """(t, length, file, gain, track, n) per sound, in time order; gains from the pack map (T `sfx`)."""
    table, lens = pk.data.get("sfx") or {}, pk.data.get("sfx_files") or {}
    rows: list[tuple] = []
    events = sorted((t, kind) for g in graphics for kind, t in g.sounds)
    for t, kind in events:
        if kind not in table:
            continue
        name, gain = table[kind]
        if kind == "beat" and any(abs(r[0] - t) < BEAT_GAP for r in rows):
            continue
        n = len(rows) + 1
        rows.append((round(max(0.0, t), 3), float(lens.get(name, 0.5)), name, gain, SFX_TRACK + n % 4, n))
    return rows


# ---- index.html ----


def host(g: Graphic, a: float = 0.0) -> str:
    nested = ' style="position:absolute;inset:0"' if g.layer == "behind" else ""
    return (
        f'      <div id="{g.id}" class="clip" data-composition-id="{g.id}" data-composition-src="compositions/{g.id}.html" '
        f'data-start="{g.start - a:.3f}" data-duration="{g.dur:.3f}" data-track-index="{g.track}" '
        f'data-track-kind="graphics" data-width="1920" data-height="1080"{nested}></div>'
    )


def frame_safe(d: float, fps: int = 60) -> str:
    """A duration string HyperFrames turns into exactly round(d x fps) frames: it takes ceil(d x fps), so
    147.5667 s (8854.002 frames) would give one frame too many and put the master's picture behind its sound.
    Exact values keep their 4-decimal text (no change, no re-render); others drop just under the frame."""
    n, text = round(d * fps), f"{d:.4f}"
    return text if float(text) * fps <= n else f"{n / fps - 1e-6:.6f}"


def index_html(plan, graphics, sfx, pk, edl, lang: str, a: float = 0.0, b: float | None = None) -> str:
    """Root composition for program time [a, b): the whole film, or one render chunk shifted by -a (T `index`)."""
    b = plan.total if b is None else b

    def inside(s0: float) -> bool:
        return a - 1e-6 <= s0 < b - 1e-6

    gs = [g for g in graphics if inside(g.start)]
    behind = "\n".join(host(g, a) for g in gs if g.layer == "behind")
    mattes = "\n".join(
        f'        <video id="{g.matte}" src="media/{g.matte}.webm" muted playsinline data-start="{g.start - a:.3f}" '
        f'data-duration="{g.dur:.3f}" data-track-index="{MATTE_TRACK}"></video>'
        for g in gs
        if g.matte
    )
    front = "\n".join(host(g, a) for g in gs if g.layer == "front")
    audio = "\n".join(
        f'      <audio id="sfx-{n}" src="assets/sfx/{name}.mp3" data-start="{t - a:.3f}" data-duration="{ln}" '
        f'data-track-index="{tr}" data-volume="{gain}"></audio>'
        for t, ln, name, gain, tr, n in sfx
        if inside(t)
    )
    zs = [z for z in plan.zooms if z[0] <= a][-1:]
    zl = [
        f'      tl.set("#cam", {{ scale: {z}, transformOrigin: "{ox:.0f}px {oy:.0f}px" }}, 0);'
        for _, z, ox, oy in zs
    ]
    zl += [
        f'      tl.set("#cam", {{ scale: {z}, transformOrigin: "{ox:.0f}px {oy:.0f}px" }}, {t - a:.3f});'
        for t, z, ox, oy in plan.zooms
        if a < t < b
    ]
    fo = {"blur": 20, "brightness": 0.42, "in": 0.3, "out": 0.35, **(pk.data.get("focus") or {})}
    on = f'filter: "blur({fo["blur"]}px) brightness({fo["brightness"]})"'
    fl = [
        f'      tl.to("#cam", {{ {on}, duration: {fo["in"]}, ease: "power2.out" }}, {s0 - a:.3f});\n'
        f'      tl.to("#cam", {{ filter: "blur(0px) brightness(1)", duration: {fo["out"]}, ease: "power2.in" }}, '
        f"{e0 - a - fo['out']:.3f});"
        for s0, e0 in plan.focus
        if inside(s0)
    ]
    fade = ""
    if edl.fade_start is not None and inside(edl.fade_start):
        fd = max(0.1, round(plan.total - edl.fade_start, 3))
        fade = (
            f'      tl.fromTo("#fade", {{ opacity: 0 }}, {{ opacity: 1, duration: {fd}, ease: "power2.out" }}, '
            f"{edl.fade_start - a:.3f});"
        )
    dur = b - a
    font = (pk.data.get("font") or {}).get("text", "sans-serif")
    return f"""<!doctype html>
<html lang="{lang}">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="assets/gsap.min.js"></script>
    <style>
{pages.font_faces(pk)}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ margin: 0; width: 1920px; height: 1080px; overflow: hidden; background: #000; }}
      #root {{ position: relative; width: 100%; height: 100%; overflow: hidden; font-family: {font}; background: #000; }}
      #cam {{ position: absolute; inset: 0; overflow: hidden; }}
      #cam video {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }}
      #fade {{ position: absolute; inset: 0; background: #000; opacity: 0; pointer-events: none; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{frame_safe(dur)}" data-width="1920" data-height="1080">
      <div id="cam">
        <video id="program" src="media/program.mp4" playsinline data-has-audio="true" data-start="0" data-media-start="{a:.4f}" data-duration="{frame_safe(dur)}" data-track-index="0"></video>
        <!-- layer: behind (under the cut-out) -->
{behind}
        <!-- cut-outs: the person over the big words -->
{mattes}
      </div>
      <!-- layer: front -->
{front}
      <!-- sound effects -->
{audio}
      <div id="fade"></div>
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      // punch-ins on camera jump cuts
{chr(10).join(zl)}
      // full-frame scenes: the A-roll blurs and dims behind them
      tl.set("#cam", {{ filter: "blur(0px) brightness(1)" }}, 0);
{chr(10).join(fl)}
      // fade to black over running footage as the last word ends
{fade}
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""


def chunk_bounds(busy: list[tuple[float, float]], total: float, target: float = CHUNK) -> list[float]:
    """Cut points for chunked 4K rendering on the 1/30 s grid, about every `target` seconds, where only the
    A-roll is on screen or sounding (T `chunk_bounds`)."""

    def free(t: float) -> bool:
        return all(not (s0 - 0.25 <= t <= e0 + 0.25) for s0, e0 in busy)

    cuts, t = [0.0], target
    while t < total - 40:
        best = None
        for k in range(1800):  # search outward up to 60 s
            for c in (t + k / 30, t - k / 30):
                c = round(c * 30) / 30
                if cuts[-1] + 40 < c < total - 20 and free(c):
                    best = c
                    break
            if best is not None:
                break
        if best is None:
            break
        cuts.append(round(best, 4))
        t = best + target
    return [*cuts, round(total, 4)]


# ---- files ----


def write_chunks(hf: Path, bounds: list[float], plan, graphics, sfx, pk, edl, lang: str) -> None:
    """`chunks/chunk-NN.html` (the root composition of each 4K render chunk) and `chunks.json`: bounds plus
    the cut-out ranges the 4K render needs (`vedit render` reads both; it never re-plans)."""
    d = hf / "chunks"
    names = []
    for i, (a, b) in enumerate(itertools.pairwise(bounds)):
        names.append(f"chunk-{i:02d}.html")
        write_if_changed(d / names[-1], index_html(plan, graphics, sfx, pk, edl, lang, a, b))
    for f in d.glob("chunk-*.html"):
        if f.name not in names:
            f.unlink()
    mattes = {g.matte: [round(g.start, 3), round(g.dur, 3)] for g in graphics if g.matte}
    data = {"target": CHUNK, "bounds": bounds, "total": round(plan.total, 4), "mattes": mattes}
    write_if_changed(hf / "chunks.json", json.dumps(data) + "\n")


def write_if_changed(f: Path, text: str) -> bool:
    if f.exists() and f.read_text(encoding="utf-8") == text:
        return False
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(f)
    return True


def copy_if_changed(src: Path, dst: Path) -> None:
    if dst.is_file() and not dst.is_symlink() and filecmp.cmp(src, dst, shallow=False):
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink():
        dst.unlink()
    shutil.copyfile(src, dst)


def link(src: Path, dst: Path) -> None:
    """Symlink (relative when inside the project), never a copy of a big file."""
    src = Path(src).resolve()
    try:
        target = os.path.relpath(src, dst.parent.resolve())
    except ValueError:
        target = str(src)
    if dst.is_symlink() and os.readlink(dst) == target:
        return
    if dst.is_symlink() or dst.exists():
        dst.unlink()
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.symlink_to(target)


def assets(hf: Path, packs_used: list, env: pages.Env, sfx_names: set[str]) -> None:
    """GSAP, fonts, project logos and sound files the compositions name, copied into hf/assets/ (small files).
    GSAP is the bundled copy (vedit/vendor/gsap): a render never fetches from a CDN."""
    copy_if_changed(GSAP_JS, hf / "assets" / "gsap.min.js")
    for pk in packs_used:
        for f in pk.data.get("fonts") or []:
            src = pk.file(f["file"])
            if src is not None:
                copy_if_changed(src, hf / "assets" / "fonts" / Path(f["file"]).name)
        for name in sfx_names:
            src = pk.file(f"sfx/{name}.mp3")
            if src is not None:
                copy_if_changed(src, hf / "assets" / "sfx" / f"{name}.mp3")
    for f in env.custom_logos.values():
        copy_if_changed(f, hf / "assets" / "logos" / f.name)


PROJECT_FILES = {
    "hyperframes.json": {
        "$schema": "https://hyperframes.heygen.com/schema/hyperframes.json",
        "paths": {"blocks": "compositions", "assets": "assets"},
        "media": {"autoProxy": False},
    },
}


def write(paths, plan, packs_for, main_pack, edl, env: pages.Env, mattes: dict[str, Path]) -> Result:
    """Write `.vedit/hf/`. packs_for(cue) -> the cue's Pack. mattes: cut-out name -> webm (big words)."""
    hf = Path(paths.hf)
    comp = hf / "compositions"
    comp.mkdir(parents=True, exist_ok=True)
    mf = hf / "manifest.json"
    try:
        old = json.loads(mf.read_text()).get("comps", {}) if mf.exists() else {}
    except ValueError:
        old = {}
    new, written, reused, graphics = {}, [], [], []
    media: dict[str, Path] = {"media/program.mp4": Path(paths.program) / "proxy.mp4"}
    sounds_of = {}
    for p in plan.items:
        pk = packs_for(p.cue)
        k = pages.key(p, pk, env)
        f = comp / f"{p.id}.html"
        prev = old.get(p.id) or {}
        if prev.get("key") == k and f.is_file():
            reused.append(p.id)
            sounds, med = prev.get("sounds", []), {r: Path(s) for r, s in prev.get("media", {}).items()}
        else:
            pg = pages.render(p, pk, env)
            write_if_changed(f, pg.html)
            written.append(p.id)
            sounds, med = pg.sounds, pg.media
        new[p.id] = {
            "key": k,
            "sounds": [list(s) for s in sounds],
            "media": {r: str(s) for r, s in med.items()},
        }
        media.update(med)
        sounds_of[p.id] = sounds
        layer, track = layer_of(p)
        g = Graphic(
            p.id, p.cue.type, p.start, p.dur, layer, track, [(kind, p.start + t) for kind, t in sounds]
        )
        if p.cue.type == "big-number":
            g.matte = f"mt-{p.id}"
            media[f"media/{g.matte}.webm"] = mattes[g.matte]
        graphics.append(g)
    assign_scene_tracks(graphics)
    removed = []
    for f in comp.glob("*.html"):
        if f.stem not in new:
            f.unlink()
            removed.append(f.stem)
    sfx = place_sfx(graphics, main_pack)
    packs_used = list({id(pk): pk for pk in [main_pack, *(packs_for(p.cue) for p in plan.items)]}.values())
    assets(hf, packs_used, env, {r[2] for r in sfx})
    if any(p.cue.type == "custom" for p in plan.items):
        link(Path(paths.custom), hf / "custom")
    for rel, src in media.items():
        link(src, hf / rel)
    for f in (hf / "media").glob("*"):
        if f"media/{f.name}" not in media and f.is_symlink():
            f.unlink()
    for name, data in PROJECT_FILES.items():
        write_if_changed(hf / name, json.dumps(data, indent=2) + "\n")
    changed = write_if_changed(hf / "index.html", index_html(plan, graphics, sfx, main_pack, edl, env.lang))
    busy = [(g.start, g.start + g.dur) for g in graphics] + [(r[0], r[0] + r[1]) for r in sfx]
    busy += list(plan.focus) + [(z[0] - 0.1, z[0] + 0.1) for z in plan.zooms]
    if edl.fade_start is not None:
        busy.append((edl.fade_start, plan.total))
    bounds = chunk_bounds(busy, plan.total)
    write_chunks(hf, bounds, plan, graphics, sfx, main_pack, edl, env.lang)
    write_if_changed(mf, json.dumps({"comps": new}, indent=1, ensure_ascii=False) + "\n")
    return Result(graphics, sfx, written, reused, removed, bounds, changed)
