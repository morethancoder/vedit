"""Big word behind the head: size and place it so the head covers at most one letter (T build.py `big_layout`).

The word sits on the roomier side of the head. The letter next to the head is tucked up to `tuck` (45 %) behind
it at his median position, and never more than one letter even at the closest his head comes in the window.
Text width comes from the pack's per-font advance table (em per character), never from a browser.
"""

from __future__ import annotations

from vedit.graphics.place import W, zoomed

DEFAULTS = {"track": -0.03, "min_px": 110, "max_px": 300, "tuck": 0.45}
EDGE = 130  # px kept clear at the frame edge on the outer side (T: 130 left, 1790 right)


def text_em(word: str, adv: dict[str, float], track: float) -> float:
    return sum(adv.get(ch, 0.6) + track for ch in word)


def is_rtl_word(word: str) -> bool:
    """True when the word's letters are Arabic-script (hebrew too) and none Latin: it displays right to left."""
    rtl = sum("\u0590" <= ch <= "\u08ff" for ch in word)
    return rtl > 0 and not any(ch.isascii() and ch.isalpha() for ch in word)


def _med(v):
    return sorted(v)[len(v) // 2]


def _pct(v, q):
    return sorted(v)[min(len(v) - 1, int(q * len(v)))]


def big_layout(
    start: float, dur: float, word: str, track, zooms, adv: dict, params: dict | None = None
) -> dict:
    """{side, fs, left, top, width, tuck, drift} for a big word over [start, start+dur] in 1920x1080 px."""
    p = {**DEFAULTS, **(params or {})}
    tr = p["track"]
    boxes = [zoomed(b, t, zooms) for t, b in track.samples(start, start + dur)]
    cx0 = _med([b[0] + b[2] / 2 for b in boxes])
    boxes = [b for b in boxes if abs(b[0] + b[2] / 2 - cx0) < 1.2 * b[2]] or boxes  # drop stray detections
    hl = [b[0] - 0.12 * b[2] for b in boxes]
    hr = [b[0] + 1.12 * b[2] for b in boxes]
    cx = _med([b[0] + b[2] / 2 for b in boxes])
    cy = _med([b[1] + b[3] * 0.45 for b in boxes])
    side = "left" if cx > W / 2 else "right"  # the word on the roomier side of the head
    # the letter that goes behind the head, by its visual edge: the template sets `direction: ltr`, but an Arabic
    # word still runs right to left inside it, so its visual right end is its first character
    vis = word[::-1] if is_rtl_word(word) else word
    inner = vis[-1] if side == "left" else vis[0]
    letter, total = adv.get(inner, 0.6) + tr, text_em(word, adv, tr)
    if side == "left":
        edge = _med(hl)
        drift, room = edge - _pct(hl, 0.1), edge - EDGE
    else:
        edge = _med(hr)
        drift, room = _pct(hr, 0.9) - edge, (W - EDGE) - edge
    tuck = p["tuck"]
    fs = p["min_px"]
    for _ in range(3):
        fs = min(float(p["max_px"]), max(float(p["min_px"]), room / (total - tuck * letter)))
        tuck = max(0.0, min(p["tuck"], (0.95 * letter * fs - drift) / (letter * fs)))
    width = total * fs
    left = edge + tuck * letter * fs - width if side == "left" else edge - tuck * letter * fs
    return {
        "side": side,
        "fs": round(fs),
        "left": round(left),
        "top": round(cy - 0.53 * fs),
        "width": round(width),
        "tuck": round(tuck, 2),
        "drift": round(drift),
    }
