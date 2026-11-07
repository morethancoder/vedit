"""Burned-in word captions for short-form outputs (reels, shorts, stories, posts).

Pages of words in reading order, at most CAPTION_LINES lines that fit the safe box width (measured with the
pack's font advances), cut at pauses >= PAGE_GAP and at sentence ends. A page shows from its first word to the
next page; the word being spoken takes the accent colour. The block sits at the bottom of the output's safe box
(above every platform's caption/username area) and hides during `pauses` (a graphic needs the room).

One sub-composition, `compositions/captions.html`, spans the whole output on its own track.
"""

from __future__ import annotations

from html import escape

from vedit.formats import layout as lay
from vedit.graphics import pages
from vedit.graphics.big import text_em

PAGE_GAP = 0.45  # s of silence that starts a new page
MAX_WORDS = 7  # words on one page at most (fast talkers)
MAX_PAGE = 3.2  # s a page stays at most
TRACK = 12  # HyperFrames track of the caption host
FILL = 0.92  # share of the safe box width a line may use


def pages_of(words: list[dict], width_px: float, adv: dict, fs: float = lay.CAPTION_PX) -> list[list[dict]]:
    """Group program words into caption pages that fit CAPTION_LINES lines of `width_px`."""
    out: list[list[dict]] = []
    cur: list[dict] = []
    lines, line_w = 1, 0.0
    space = adv.get(" ", 0.28) * fs
    for w in words:
        text = str(w.get("w", "")).strip()
        if not text:
            continue
        ww = text_em(text, adv, 0.0) * fs
        gap = cur and (w["t0"] - cur[-1]["t1"] >= PAGE_GAP or str(cur[-1]["w"]).rstrip()[-1:] in ".?!؟")
        long = cur and (len(cur) >= MAX_WORDS or w["t1"] - cur[0]["t0"] > MAX_PAGE)
        fits_line = line_w + (space if line_w else 0) + ww <= width_px
        if cur and (gap or long or (not fits_line and lines >= lay.CAPTION_LINES)):
            out.append(cur)
            cur, lines, line_w = [], 1, 0.0
        elif cur and not fits_line:
            lines, line_w = lines + 1, 0.0
        cur.append(w)
        line_w += (space if line_w else 0) + ww
    if cur:
        out.append(cur)
    return out


def _hidden(t0: float, t1: float, pauses: list[tuple[float, float]]) -> bool:
    return any(t0 < e and t1 > s for s, e in pauses)


def page_html(geo: lay.Geometry, words: list[dict], pauses, pk, accent: str | None, lang: str) -> str:
    """The caption sub-composition for [geo.t0, geo.t1) (times local to the output)."""
    a, b = geo.t0, geo.t1
    w, h = geo.canvas
    inside = [x for x in words if a <= x["t0"] < b]
    cx0, cx1 = geo.clear(geo.caption_top, geo.safe.y1)
    pgs = pages_of(inside, (cx1 - cx0) * FILL, pk.advances())
    c = pages.colors(pk, accent)
    font = (pk.data.get("font") or {}).get("text", "sans-serif")
    rtl = lang.split("-")[0] in pages.RTL_LANGS
    divs, lines = [], []
    for n, pg in enumerate(pgs):
        s0 = pg[0]["t0"] - a
        e0 = (pgs[n + 1][0]["t0"] - a) if n + 1 < len(pgs) else min(pg[-1]["t1"] + 0.6, b) - a
        e0 = min(e0, pg[-1]["t1"] - a + 1.2)
        if _hidden(s0 + a, e0 + a, pauses):
            continue
        spans = " ".join(f'<span class="w" id="cw{n}-{k}">{escape(str(x["w"]).strip())}</span>'
                         for k, x in enumerate(pg))  # fmt: skip
        divs.append(f'<div class="pg" id="cp{n}" dir="{"rtl" if rtl else "ltr"}">{spans}</div>')
        lines.append(f'        tl.set(q("#cp{n}"), {{ opacity: 1 }}, {s0:.3f});')
        lines.append(f'        tl.set(q("#cp{n}"), {{ opacity: 0 }}, {e0:.3f});')
        for k, x in enumerate(pg):
            lines.append(
                f'        tl.set(q("#cw{n}-{k}"), {{ color: "{c.get("accent", "#FFD60A")}" }}, {x["t0"] - a:.3f});'
            )
            lines.append(
                f'        tl.set(q("#cw{n}-{k}"), {{ color: "#FFFFFF" }}, {max(x["t1"], x["t0"] + 0.08) - a:.3f});'
            )
    css = f"""
      .capline {{ position: absolute; left: {cx0:.0f}px; width: {cx1 - cx0:.0f}px; top: {geo.caption_top:.0f}px;
        height: {geo.caption_h:.0f}px; display: flex; align-items: center; justify-content: center; }}
      .pg {{ position: absolute; inset: 0; display: flex; flex-wrap: wrap; align-content: center; justify-content: center;
        gap: 0 0.28em; opacity: 0; text-align: center; font: 800 {lay.CAPTION_PX}px/1.25 {font}; color: #FFFFFF;
        -webkit-text-stroke: 2px rgba(0,0,0,.55); paint-order: stroke fill;
        text-shadow: 0 3px 6px rgba(0,0,0,.6), 0 8px 30px rgba(0,0,0,.45); }}
      .w {{ display: inline-block; }}"""
    body = f'        <div class="capline">{"".join(divs)}</div>'
    html = pages.page("captions", pages.font_faces(pk), css, body, "\n".join(lines), (w, h))
    return html.replace("const D = DUR;", f"const D = {b - a:.3f};")


def host(geo: lay.Geometry) -> str:
    w, h = geo.canvas
    return (
        f'      <div id="captions" class="clip" data-composition-id="captions" data-composition-src="compositions/captions.html" '
        f'data-start="0" data-duration="{geo.t1 - geo.t0:.3f}" data-track-index="{TRACK}" data-track-kind="graphics" '
        f'data-width="{w}" data-height="{h}"></div>'
    )
