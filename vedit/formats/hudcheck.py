"""HUD check: does any graphic or caption box of an output run into a target platform's on-screen UI?

Reads `.vedit/out/<id>/hf/manifest.json` (`slots`: graphic id -> box in output px, written by compose_out) and
tests each box against `formats.hud()` for every platform of the output. Edge margins (bars built from side
insets when a platform publishes no regions) only count for text; a full-width card may run to the frame edge.
`mock()` draws the platform UI over a frame so a person can see it.
"""

from __future__ import annotations

import json
from pathlib import Path

from vedit import formats as fm

MIN_SHARE = 0.02  # a box must lose at least this share of its area to a region to be flagged
EDGES = {"left edge", "right edge"}


def check(slots: dict[str, dict], platforms: list[str], size: tuple[int, int], cards: set[str]) -> list[dict]:
    """[{id, platform, region, share}] for every box that enters a HUD region."""
    out = []
    for gid, b in slots.items():
        box = fm.Box(b["x"], b["y"], b["w"], b["h"])
        area = max(1.0, box.w * box.h)
        for pid in platforms:
            for reg in fm.hud(pid, size):
                if gid in cards and reg["name"] in EDGES:
                    continue
                share = box.overlap(reg["box"]) / area
                if share >= MIN_SHARE:
                    out.append({"id": gid, "platform": pid, "region": reg["name"], "share": round(share, 3)})
    return out


def check_output(hf: Path) -> tuple[dict, list[dict]]:
    """(manifest output dict, flags) for one built output project."""
    mf = json.loads((hf / "manifest.json").read_text())
    out = mf["output"]
    size = fm.canvas(out["aspect"])
    slots = dict(mf.get("slots") or {})
    cards = set(mf.get("cards") or [])
    return out, check(slots, out["platforms"], size, cards)


def mock(img, platforms: list[str]):
    """Draw each platform's HUD regions (translucent red, labelled) over an output-sized BGR frame."""
    import cv2

    h, w = img.shape[:2]
    over = img.copy()
    for pid in platforms:
        for reg in fm.hud(pid, (w, h)):
            b = reg["box"]
            p0, p1 = (int(b.x), int(b.y)), (int(b.x1), int(b.y1))
            cv2.rectangle(over, p0, p1, (40, 40, 220), -1)
            cv2.putText(over, f"{pid}: {reg['name']}", (p0[0] + 8, p0[1] + 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                        (255, 255, 255), 2)  # fmt: skip
    out = cv2.addWeighted(over, 0.35, img, 0.65, 0)
    sb = fm.safe_box(platforms, (w, h))
    cv2.rectangle(out, (int(sb.x), int(sb.y)), (int(sb.x1), int(sb.y1)), (0, 220, 0), 4)
    return out


def mock_sheet(video: Path, platforms: list[str], dst: Path, n: int = 6) -> Path:
    """n frames of an output render with the HUD drawn on, side by side."""
    import cv2
    import numpy as np

    vid = cv2.VideoCapture(str(video))
    frames = int(vid.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    tiles = []
    for k in range(n):
        vid.set(cv2.CAP_PROP_POS_FRAMES, int(frames * (k + 0.5) / n))
        ok, img = vid.read()
        if not ok:
            continue
        m = mock(img, platforms)
        tiles.append(cv2.resize(m, (360, round(360 * m.shape[0] / m.shape[1]))))
    vid.release()
    if not tiles:
        raise ValueError(f"no frames read from {video}")
    cv2.imwrite(str(dst), np.hstack(tiles), [cv2.IMWRITE_JPEG_QUALITY, 85])
    return dst
