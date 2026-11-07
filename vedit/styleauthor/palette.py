"""Palette of reference images (OpenCV k-means in CIE Lab, no ML) and its distance to a pack's colours.

Distance (`distance`): for every hex colour of the pack's `colors` (keys `ref*` excluded, they are the clusters
themselves), the CIE76 ΔE (Euclidean in Lab, L 0-100) to the nearest reference cluster; the reported number is
the mean of those (small saturated clusters count: k is 10 and clusters >= 0.2% of the pixels are kept, so a
small accent has its own cluster to be measured against). ΔE < 2.3 is a just-noticeable difference, ~10 is clearly another shade, > 25 another colour.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

K = 10  # clusters per palette (high enough that a small accent gets its own)
MAX_SIDE = 160  # each image is shrunk to this before its pixels are pooled
MIN_WEIGHT = 0.002  # clusters under this share of the pixels (0.2%) are dropped as noise
MIN_CHROMA = 20.0  # Lab chroma a cluster needs to be the accent: a big grey background never is
IVORY_L, INK_L = 80.0, 25.0  # Lab lightness a cluster needs to replace ivory / ink
HEX = re.compile(r"^#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})$")


@dataclass
class Cluster:
    hex: str
    weight: float  # share of the pooled pixels
    lab: tuple[float, float, float]

    @property
    def chroma(self) -> float:
        return float(np.hypot(self.lab[1], self.lab[2]))

    def to_dict(self) -> dict:
        return {"hex": self.hex, "weight": round(self.weight, 3), "lab": [round(x, 1) for x in self.lab]}


def _lab(rgb01: np.ndarray) -> np.ndarray:
    """N x 3 RGB in [0, 1] -> N x 3 Lab (L 0-100)."""
    return cv2.cvtColor(rgb01.reshape(-1, 1, 3).astype(np.float32), cv2.COLOR_RGB2Lab).reshape(-1, 3)


def _rgb(lab: np.ndarray) -> np.ndarray:
    out = cv2.cvtColor(np.asarray(lab, np.float32).reshape(-1, 1, 3), cv2.COLOR_Lab2RGB).reshape(-1, 3)
    return np.clip(out, 0, 1)


def hex_of(rgb01) -> str:
    r, g, b = (round(float(x) * 255) for x in rgb01)
    return f"#{r:02X}{g:02X}{b:02X}"


def lab_of_hex(h: str) -> np.ndarray:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    rgb = np.array([int(h[i : i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)
    return _lab(rgb)[0]


def pixels(path: Path) -> np.ndarray:
    """An image's pixels as N x 3 Lab, shrunk to MAX_SIDE (alpha-transparent pixels dropped)."""
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        return np.zeros((0, 3), np.float32)
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    h, w = img.shape[:2]
    s = min(1.0, MAX_SIDE / max(h, w))
    if s < 1:
        img = cv2.resize(img, (max(1, round(w * s)), max(1, round(h * s))), interpolation=cv2.INTER_AREA)
    px = img.reshape(-1, img.shape[2])
    if px.shape[1] == 4:
        px = px[px[:, 3] > 127]
    rgb = px[:, :3][:, ::-1].astype(np.float32) / 255.0
    return _lab(rgb)


def extract(images: list[Path], k: int = K) -> list[Cluster]:
    """k-means clusters of the pooled pixels of `images`, biggest first (deterministic: fixed seed)."""
    data = np.concatenate([pixels(p) for p in images] or [np.zeros((0, 3), np.float32)])
    if len(data) == 0:
        return []
    k = max(1, min(k, len(np.unique(data.round(1), axis=0))))
    cv2.setRNGSeed(0)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.2)
    _, labels, centers = cv2.kmeans(data.astype(np.float32), k, None, crit, 4, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.ravel(), minlength=k)
    rgbs = _rgb(centers)
    out = [
        Cluster(hex_of(rgbs[i]), counts[i] / len(data), tuple(float(x) for x in centers[i]))
        for i in range(k)
        if counts[i] / len(data) >= MIN_WEIGHT
    ]
    return sorted(out, key=lambda c: -c.weight)


def guess(clusters: list[Cluster]) -> dict[str, str]:
    """accent = the most saturated cluster with Lab chroma >= MIN_CHROMA, however small (none: base keeps its
    accent); ivory = the lightest when it is light
    enough to read as text (L >= IVORY_L), ink = the darkest when dark enough (L <= INK_L). A colour left out
    keeps the base value (a talking head's lightest cluster is often skin, not paper)."""
    if not clusters:
        return {}
    out = {}
    vivid = [c for c in clusters if c.chroma >= MIN_CHROMA]
    if vivid:
        out["accent"] = max(vivid, key=lambda c: c.chroma).hex
    light, dark = max(clusters, key=lambda c: c.lab[0]), min(clusters, key=lambda c: c.lab[0])
    if light.lab[0] >= IVORY_L:
        out["ivory"] = light.hex
    if dark.lab[0] <= INK_L:
        out["ink"] = dark.hex
    return out


def delta_e(a: str, b: str) -> float:
    return float(np.linalg.norm(lab_of_hex(a) - lab_of_hex(b)))


def pack_colors(colors: dict) -> dict[str, str]:
    """The pack's hex colours that are its own choices (not the `ref*` palette copied from the refs)."""
    return {
        str(k): str(v)
        for k, v in (colors or {}).items()
        if isinstance(v, str) and HEX.match(v.strip()) and not str(k).startswith("ref")
    }


def distance(colors: dict, clusters: list[Cluster]) -> dict | None:
    """{mean, per: {name: {hex, nearest, de}}}; None without clusters or colours."""
    own = pack_colors(colors)
    if not clusters or not own:
        return None
    per = {}
    for name, h in own.items():
        near = min(clusters, key=lambda c: delta_e(h, c.hex))
        per[name] = {"hex": h, "nearest": near.hex, "de": round(delta_e(h, near.hex), 1)}
    return {"mean": round(sum(p["de"] for p in per.values()) / len(per), 1), "per": per}
