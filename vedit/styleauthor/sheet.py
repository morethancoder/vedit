"""PNG sheets (OpenCV): one pack's specimen beside its refs, and several packs side by side.

Labels are ASCII (pack names, type ids, hex): the sample text itself is in the tiles, drawn by the browser.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

BG = (24, 22, 20)  # BGR, near-black
FG = (235, 240, 242)
DIM = (150, 150, 150)
WARN = (60, 170, 240)
FONT = cv2.FONT_HERSHEY_SIMPLEX


def _bgr(hexs: str) -> tuple[int, int, int]:
    h = hexs.lstrip("#")
    return int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)


def text(img, s: str, x: int, y: int, scale: float = 0.8, color=FG, thick: int = 2) -> None:
    s = s.encode("ascii", "replace").decode()
    cv2.putText(img, s, (x, y), FONT, scale, color, thick, cv2.LINE_AA)


def fit(img: np.ndarray, w: int, h: int) -> np.ndarray:
    """Letterboxed into w x h on the sheet colour."""
    out = np.full((h, w, 3), BG, np.uint8)
    ih, iw = img.shape[:2]
    s = min(w / iw, h / ih)
    nw, nh = max(1, round(iw * s)), max(1, round(ih * s))
    small = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_AREA)
    y, x = (h - nh) // 2, (w - nw) // 2
    out[y : y + nh, x : x + nw] = small
    return out


def read(f: Path | None) -> np.ndarray | None:
    if f is None or not Path(f).is_file():
        return None
    img = cv2.imread(str(f), cv2.IMREAD_COLOR)
    return img


def tile(label: str, f: Path | None, w: int, h: int, note: str = "") -> np.ndarray:
    """A labelled tile: a strip with the label over the image (or the note, when there is no image)."""
    strip = 40
    out = np.full((h + strip, w, 3), BG, np.uint8)
    text(out, label, 10, 28, 0.75)
    img = read(f)
    if img is not None:
        out[strip:] = fit(img, w, h)
    else:
        cv2.rectangle(out, (0, strip), (w - 1, h + strip - 1), DIM, 1)
        text(out, "not rendered", 16, strip + 40, 0.7, WARN)
        for i, ln in enumerate(_wrap(note, w // 13)[:6]):
            text(out, ln, 16, strip + 80 + 30 * i, 0.55, DIM, 1)
    return out


def _wrap(s: str, n: int) -> list[str]:
    words, lines, cur = s.split(), [], ""
    for wd in words:
        if len(cur) + len(wd) + 1 > n and cur:
            lines.append(cur)
            cur = wd
        else:
            cur = f"{cur} {wd}".strip()
    return lines + ([cur] if cur else [])


def grid(tiles: list[np.ndarray], cols: int, pad: int = 16) -> np.ndarray:
    if not tiles:
        return np.full((10, 10, 3), BG, np.uint8)
    th, tw = tiles[0].shape[:2]
    rows = (len(tiles) + cols - 1) // cols
    out = np.full((rows * (th + pad) + pad, cols * (tw + pad) + pad, 3), BG, np.uint8)
    for i, t in enumerate(tiles):
        r, c = divmod(i, cols)
        y, x = pad + r * (th + pad), pad + c * (tw + pad)
        out[y : y + th, x : x + tw] = t
    return out


def swatches(colors: list[tuple[str, str]], width: int, h: int = 44) -> np.ndarray:
    """A row of colour chips, each `name #hex` under it."""
    out = np.full((h + 34, width, 3), BG, np.uint8)
    x = 16
    for name, hx in colors:
        if x + 150 > width:
            break
        cv2.rectangle(out, (x, 4), (x + 140, 4 + h), _bgr(hx), -1)
        cv2.rectangle(out, (x, 4), (x + 140, 4 + h), DIM, 1)
        text(out, f"{name} {hx}"[:20], x, h + 28, 0.45, FG, 1)
        x += 156
    return out


def stack(parts: list[np.ndarray]) -> np.ndarray:
    w = max(p.shape[1] for p in parts)
    padded = [np.pad(p, ((0, 0), (0, w - p.shape[1]), (0, 0)), constant_values=0) for p in parts]
    for p, src in zip(padded, parts, strict=True):
        p[:, src.shape[1] :] = BG
    return np.vstack(padded)


def specimen(
    title: str, tiles: list[tuple[str, Path | None, str]], refs: list[Path], colors, clusters, out: Path
) -> Path:
    """Tiles in 3 columns (640x360), the refs in a column on the right, pack colours and ref clusters on top."""
    body = grid([tile(lb, f, 640, 360, note) for lb, f, note in tiles], 3)
    if refs:
        rcol = [
            fit(img, 520, 520 * img.shape[0] // img.shape[1])
            for img in (read(r) for r in refs)
            if img is not None
        ]
        col = np.full((body.shape[0], 552, 3), BG, np.uint8)
        y = 56
        text(col, "refs", 16, 36, 0.8)
        for img in rcol:
            if y + img.shape[0] > col.shape[0]:
                break
            col[y : y + img.shape[0], 16 : 16 + img.shape[1]] = img
            y += img.shape[0] + 16
        body = np.hstack([body, col])
    head = np.full((64, body.shape[1], 3), BG, np.uint8)
    text(head, title, 16, 44, 1.1, FG, 2)
    parts = [head, swatches(colors, body.shape[1])]
    if clusters:
        parts.append(swatches(clusters, body.shape[1]))
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), stack([*parts, body]))
    return out


def compare(packs: list[tuple[str, dict[str, tuple[Path | None, str]]]], order: list[str], out: Path) -> Path:
    """Packs side by side: one column per pack (name on top), one row per specimen tile in `order`."""
    w, h, pad, label_w = 640, 360, 16, 200
    head = np.full((90, label_w + len(packs) * (w + pad) + pad, 3), BG, np.uint8)
    for j, (name, _) in enumerate(packs):
        for i, ln in enumerate(_wrap(name, 40)[:2]):
            text(head, ln, label_w + pad + j * (w + pad), 40 + 36 * i, 1.0, FG, 2)
    rows = [head]
    for tid in order:
        cells = []
        for _, tiles in packs:
            f, note = tiles.get(tid) or (None, "not in this specimen")
            cells.append(tile("", f, w, h, note))
        row = grid(cells, len(cells), pad)
        lab = np.full((row.shape[0], label_w, 3), BG, np.uint8)
        text(lab, tid, 16, pad + 70, 0.8, FG, 2)
        rows.append(np.hstack([lab, row]))
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), stack(rows))
    return out
