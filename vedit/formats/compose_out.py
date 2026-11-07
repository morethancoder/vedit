"""Write one non-master output's HyperFrames project: `.vedit/out/<id>/hf/` (see vedit.formats.layout).

The plan is the master's (same cues, same windows); this module only re-frames it: the span [t0, t1) of the
program, the canvas, the pan along the reframe path, and each graphic's place in the new frame. Compositions are
rendered from the unshifted placements (their animation is local to their own start), and the root composition
offsets every host by -t0, as a 4K render chunk does.
"""

from __future__ import annotations

import dataclasses
import itertools
import json
from dataclasses import dataclass, field
from pathlib import Path

from vedit.formats import layout as lay
from vedit.graphics import compose, pages
from vedit.graphics.compose import (
    BEHIND_TRACK,
    FRONT_TRACK,
    MATTE_TRACK,
    PROJECT_FILES,
    SCENE_TRACK,
    Graphic,
    assign_scene_tracks,
    frame_safe,
    place_sfx,
    write_if_changed,
)
from vedit.graphics.plan import _em


@dataclass
class OutResult:
    oid: str
    hf: Path
    graphics: list[Graphic]
    written: list[str]
    reused: list[str]
    pauses: list[tuple[float, float]]  # program-time windows where the burned-in captions pause
    slots: dict[str, dict] = field(default_factory=dict)  # graphic id -> its box in the output (HUD check)
    t0: float = 0.0
    t1: float = 0.0
    captioned: bool = False
    wants_captions: bool = False


def out_dir(paths, oid: str) -> Path:
    return Path(paths.vedit) / "out" / oid / "hf"


def _in_span(p, t0: float, t1: float) -> bool:
    return t0 - 1e-6 <= p.start < t1 - 0.25


def _pan_lines(geo: lay.Geometry, a: float) -> list[str]:
    """GSAP for the #frame pan: a set at every cut and at the start, a linear tween over each moving stretch."""
    pts = geo.points
    lines = [f'      tl.set("#frame", {{ x: {-pts[0]["x"] * geo.s:.1f} }}, 0);']
    for p, q in itertools.pairwise(pts):
        if q.get("cut"):
            lines.append(f'      tl.set("#frame", {{ x: {-q["x"] * geo.s:.1f} }}, {q["t"] - a:.3f});')
        elif abs(q["x"] - p["x"]) > 0.05:
            lines.append(
                f'      tl.to("#frame", {{ x: {-q["x"] * geo.s:.1f}, duration: {q["t"] - p["t"]:.3f}, ease: "none" }}, '
                f"{p['t'] - a:.3f});"
            )
    return lines


def _host(g: Graphic, a: float, size: tuple[int, int], style: str = "") -> str:
    st = f' style="{style}"' if style else ""
    return (
        f'      <div id="{g.id}" class="clip" data-composition-id="{g.id}" data-composition-src="compositions/{g.id}.html" '
        f'data-start="{g.start - a:.3f}" data-duration="{g.dur:.3f}" data-track-index="{g.track}" '
        f'data-track-kind="graphics" data-width="{size[0]}" data-height="{size[1]}"{st}></div>'
    )


def index_html(
    geo: lay.Geometry, plan, graphics, cards: dict, sfx, pk, edl, lang: str, captions_html: str = ""
) -> str:
    a, b = geo.t0, geo.t1
    w, h = geo.canvas
    behind = "\n".join(compose.host(g, a) for g in graphics if g.layer == "behind")
    mattes = "\n".join(
        f'          <video id="{g.matte}" src="media/{g.matte}.webm" muted playsinline data-start="{g.start - a:.3f}" '
        f'data-duration="{g.dur:.3f}" data-track-index="{MATTE_TRACK}"></video>'
        for g in graphics
        if g.matte
    )
    front = []
    for g in graphics:
        if g.layer != "front":
            continue
        if g.id in cards:
            c = cards[g.id]
            style = (f"position:absolute;left:{c['x']}px;top:{c['y']}px;width:1920px;height:1080px;"
                     f"transform:scale({c['k']});transform-origin:0 0")  # fmt: skip
            front.append(_host(g, a, (1920, 1080), style))
        else:
            front.append(_host(g, a, (w, h)))
    audio = "\n".join(
        f'      <audio id="sfx-{n}" src="assets/sfx/{name}.mp3" data-start="{t - a:.3f}" data-duration="{ln}" '
        f'data-track-index="{tr}" data-volume="{gain}"></audio>'
        for t, ln, name, gain, tr, n in sfx
        if a - 1e-6 <= t < b - 1e-6
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
        f'      tl.to("#cam", {{ {on}, duration: {fo["in"]}, ease: "power2.out" }}, {max(0.0, s0 - a):.3f});\n'
        f'      tl.to("#cam", {{ filter: "blur(0px) brightness(1)", duration: {fo["out"]}, ease: "power2.in" }}, '
        f"{min(e0, b) - a - fo['out']:.3f});"
        for s0, e0 in plan.focus
        if s0 < b and e0 > a
    ]
    fade = ""
    if edl.fade_start is not None and a <= edl.fade_start < b:
        fd = max(0.1, round(b - edl.fade_start, 3))
        fade = (f'      tl.fromTo("#fade", {{ opacity: 0 }}, {{ opacity: 1, duration: {fd}, ease: "power2.out" }}, '
                f"{edl.fade_start - a:.3f});")  # fmt: skip
    dur = b - a
    font = (pk.data.get("font") or {}).get("text", "sans-serif")
    return f"""<!doctype html>
<html lang="{lang}">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={w}, height={h}" />
    <script src="assets/gsap.min.js"></script>
    <style>
{pages.font_faces(pk)}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ margin: 0; width: {w}px; height: {h}px; overflow: hidden; background: #000; }}
      #root {{ position: relative; width: 100%; height: 100%; overflow: hidden; font-family: {font}; background: #000; }}
      #frame {{ position: absolute; left: 0; top: 0; width: 1920px; height: 1080px; transform-origin: 0 0; }}
      #cam {{ position: absolute; inset: 0; overflow: hidden; }}
      #cam video {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }}
      #fade {{ position: absolute; inset: 0; background: #000; opacity: 0; pointer-events: none; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{frame_safe(dur)}" data-width="{w}" data-height="{h}">
      <div id="frame">
        <div id="cam">
          <video id="program" src="media/program.mp4" playsinline data-has-audio="true" data-start="0" data-media-start="{a:.4f}" data-duration="{frame_safe(dur)}" data-track-index="0"></video>
          <!-- layer: behind (under the cut-out) -->
{behind}
          <!-- cut-outs -->
{mattes}
        </div>
      </div>
      <!-- layer: front -->
{chr(10).join(front)}
{captions_html}
      <!-- sound effects -->
{audio}
      <div id="fade"></div>
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      // the program fills the height and pans along the reframe path (vedit reframe)
      tl.set("#frame", {{ scale: {geo.s:.5f} }}, 0);
{chr(10).join(_pan_lines(geo, a))}
      // punch-ins on camera jump cuts
{chr(10).join(zl)}
      // full-frame scenes: the A-roll blurs and dims behind them
      tl.set("#cam", {{ filter: "blur(0px) brightness(1)" }}, 0);
{chr(10).join(fl)}
{fade}
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""


def write(paths, out, geo: lay.Geometry, plan, packs_for, main_pack, edl, env: pages.Env, track, mattes, words=None) -> OutResult:  # fmt: skip
    """Write `.vedit/out/<id>/hf/` for one output. `words` (program time) add burned-in captions when the
    output asks for them (vedit.formats.captions)."""
    hf = out_dir(paths, out.id)
    comp = hf / "compositions"
    comp.mkdir(parents=True, exist_ok=True)
    mf = hf / "manifest.json"
    try:
        old = json.loads(mf.read_text()).get("comps", {}) if mf.exists() else {}
    except ValueError:
        old = {}
    adv = main_pack.advances()
    new, written, reused, graphics, cards, pauses, slots = {}, [], [], [], {}, [], {}
    media: dict[str, Path] = {"media/program.mp4": Path(paths.program) / "proxy.mp4"}
    for p in plan.items:
        if not _in_span(p, geo.t0, geo.t1):
            continue
        typ = p.cue.type
        pk = packs_for(p.cue)
        q, size, css = p, (1920, 1080), ""
        end = min(p.end, geo.t1)
        if typ in lay.TEXT:
            em = _em(str(p.cue.fields.get("words", "")), adv) if typ == "kinetic" else 0.0
            slot = lay.band(geo, track, typ, p.start, end, em)
            size, css = geo.canvas, lay.wrap_css(geo, typ, slot)
            if slot.pause_captions:
                pauses.append((p.start, end))
            slots[p.id] = {"x": slot.x0, "y": slot.top, "w": slot.x1 - slot.x0, "h": slot.bottom - slot.top}
        elif typ == "big-number":
            q = dataclasses.replace(p, big=lay.big(geo, track, p.start, end, str(p.cue.fields["word"]), adv))
        elif typ in lay.CARD:
            cards[p.id] = lay.card(geo)
            c = cards[p.id]
            slots[p.id] = {"x": c["x"], "y": c["y"], "w": c["w"], "h": c["h"]}
        k = pages.key(q, pk, env, size, css)
        f = comp / f"{p.id}.html"
        prev = old.get(p.id) or {}
        if prev.get("key") == k and f.is_file():
            reused.append(p.id)
            sounds, med = prev.get("sounds", []), {r: Path(s) for r, s in prev.get("media", {}).items()}
        else:
            pg = pages.render(q, pk, env, size, css)
            write_if_changed(f, pg.html)
            written.append(p.id)
            sounds, med = pg.sounds, pg.media
        new[p.id] = {
            "key": k,
            "sounds": [list(s) for s in sounds],
            "media": {r: str(s) for r, s in med.items()},
        }
        media.update(med)
        layer, tr = compose.layer_of(p)
        g = Graphic(p.id, typ, p.start, end - p.start, layer, tr, [(kind, p.start + t) for kind, t in sounds])
        if typ == "big-number" and f"mt-{p.id}" in mattes:
            g.matte = f"mt-{p.id}"
            media[f"media/{g.matte}.webm"] = mattes[g.matte]
        graphics.append(g)
    assign_scene_tracks(graphics)
    burn = bool(words) and geo.captions
    for f in comp.glob("*.html"):
        if f.stem not in new and not (burn and f.stem == "captions"):
            f.unlink()
    sfx = place_sfx(graphics, main_pack)
    packs_used = list({id(pk): pk for pk in [main_pack, *(packs_for(p.cue) for p in plan.items)]}.values())
    compose.assets(hf, packs_used, env, {r[2] for r in sfx})
    if any(g.type == "custom" for g in graphics):
        compose.link(Path(paths.custom), hf / "custom")
    for rel, src in media.items():
        compose.link(src, hf / rel)
    for f in (hf / "media").glob("*"):
        if f"media/{f.name}" not in media and f.is_symlink():
            f.unlink()
    for name, data in PROJECT_FILES.items():
        write_if_changed(hf / name, json.dumps(data, indent=2) + "\n")
    cap_html = ""
    if burn:
        from vedit.formats import captions as capmod

        write_if_changed(
            comp / "captions.html", capmod.page_html(geo, words, pauses, main_pack, env.accent, env.lang)
        )
        cap_html = capmod.host(geo)
        cx0, cx1 = geo.clear(geo.caption_top, geo.safe.y1)
        slots["captions"] = {"x": cx0, "y": geo.caption_top, "w": cx1 - cx0, "h": geo.caption_h}
    write_if_changed(
        hf / "index.html", index_html(geo, plan, graphics, cards, sfx, main_pack, edl, env.lang, cap_html)
    )
    write_if_changed(mf, json.dumps({"comps": new, "output": out.as_dict(), "span": [geo.t0, geo.t1],
                                     "pauses": pauses, "slots": slots, "cards": sorted(cards)},
                                    indent=1, ensure_ascii=False) + "\n")  # fmt: skip
    return OutResult(out.id, hf, graphics, written, reused, pauses, slots, geo.t0, geo.t1, burn, geo.captions)


_ = (BEHIND_TRACK, FRONT_TRACK, SCENE_TRACK)  # re-exported track numbers stay importable from here
