"""Contact sheets of the peak snapshots: 12 cells a sheet (4 x 3), each labelled `<n>. <cue id>  mm:ss`.

Cells come from `styleauthor.sheet` (tile + grid). A flagged cell gets a red frame, its flag codes in the
label, and the boxes behind the flags drawn on it (red: text, orange: the face box grown by the margin), so
the eye goes to those first. Unflagged cells are the plain frame.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from vedit.styleauthor import sheet as sh

PER_SHEET = 12
COLS = 4
CELL = (640, 360)
RED = (40, 40, 230)  # BGR
ORANGE = (0, 150, 255)


def mmss(t: float) -> str:
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def where(i: int) -> tuple[int, int]:
    """(sheet number from 1, cell number from 1) of the i-th graphic in time order."""
    return i // PER_SHEET + 1, i % PER_SHEET + 1


def _cell(c: dict) -> np.ndarray:
    n, cid, t, flags = c["cell"], c["id"], c["peak"], c["flags"]
    codes = ",".join(f["code"] for f in flags)
    label = f"{n}. {cid}  {mmss(t)}" + (f"  [{codes}]" if codes else "")
    img = sh.read(c.get("shot"))
    if img is not None and flags:
        img = img.copy()
        s = img.shape[1] / 1920
        for b in c.get("marks", {}).get("text", []):
            p0, p1 = (round(b[0] * s), round(b[1] * s)), (round(b[2] * s), round(b[3] * s))
            cv2.rectangle(img, p0, p1, RED, max(2, round(4 * s)))
        fb = c.get("marks", {}).get("face")
        if fb:
            p0, p1 = (round(fb[0] * s), round(fb[1] * s)), (round(fb[2] * s), round(fb[3] * s))
            cv2.rectangle(img, p0, p1, ORANGE, max(2, round(4 * s)))
    w, h = CELL
    tile = np.full((h + 40, w, 3), sh.BG, np.uint8)
    sh.text(tile, label, 10, 28, 0.62, sh.WARN if flags else sh.FG, 2 if flags else 1)
    if img is not None:
        tile[40:] = sh.fit(img, w, h)
    else:
        sh.text(tile, "no snapshot", 16, 90, 0.7, sh.WARN)
    if flags:
        cv2.rectangle(tile, (0, 0), (w - 1, h + 39), RED, 4)
    return tile


def write(cells: list[dict], out_dir: Path, title: str) -> list[Path]:
    """One JPG per PER_SHEET cells: `sheet-01.jpg`, … Old sheets in out_dir are removed first."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for f in out_dir.glob("sheet-*.jpg"):
        f.unlink()
    files = []
    pages = [cells[i : i + PER_SHEET] for i in range(0, len(cells), PER_SHEET)]
    for k, page in enumerate(pages, 1):
        body = sh.grid([_cell(c) for c in page], COLS)
        head = np.full((60, body.shape[1], 3), sh.BG, np.uint8)
        sh.text(head, f"{title}  sheet {k}/{len(pages)}", 16, 42, 0.95, sh.FG, 2)
        f = out_dir / f"sheet-{k:02d}.jpg"
        cv2.imwrite(str(f), np.vstack([head, body]), [cv2.IMWRITE_JPEG_QUALITY, 85])
        files.append(f)
    return files
