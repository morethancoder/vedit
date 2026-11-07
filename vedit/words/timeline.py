"""The program clock: source time <-> program time over an EDL (ported from T tools/timeline.py)."""

from __future__ import annotations

import json
from pathlib import Path


class Edl:
    """pieces: [{clip, in, out, start, hold?, sound?}], total, fade_start."""

    def __init__(self, data: dict):
        self.pieces: list[dict] = list(data.get("pieces", []))
        self.total: float = data.get("total", 0.0)
        self.fade_start: float | None = data.get("fade_start")

    @classmethod
    def load(cls, path: Path | str) -> Edl:
        return cls(json.loads(Path(path).read_text()))

    @staticmethod
    def length(p: dict) -> float:
        return p.get("hold", p["out"] - p["in"])

    def _kept(self, clip: str) -> list[dict]:
        return [p for p in self.pieces if p["clip"] == clip and "hold" not in p]

    def g(self, clip: str, t: float) -> float:
        """Source time in clip -> program time; a removed range lands on the next kept frame."""
        kept = self._kept(clip)
        if not kept:
            raise ValueError(f"clip {clip!r} has no kept pieces in the EDL")
        later = None
        for p in kept:
            if p["in"] <= t < p["out"]:
                return round(p["start"] + t - p["in"], 3)
            if p["in"] > t and later is None:
                later = p
        if later is None:  # past the clip's last kept frame: its end
            last = kept[-1]
            return round(last["start"] + last["out"] - last["in"], 3)
        return round(later["start"], 3)

    def src(self, t: float) -> tuple[str, float]:
        """Program time -> (clip, source time); past the end -> the last piece's out."""
        for p in self.pieces:
            if p["start"] <= t < p["start"] + self.length(p):
                return p["clip"], (p["in"] if "hold" in p else p["in"] + t - p["start"])
        last = self.pieces[-1]
        return last["clip"], last["out"]

    def joins(self) -> list[float]:
        """Program times where one kept piece meets the next."""
        return [p["start"] for p in self.pieces[1:]]

    def holds(self) -> list[tuple[float, float]]:
        """(program start, seconds) of each chapter hold; `sound: continue` holds are not chapters."""
        return [(p["start"], p["hold"]) for p in self.pieces if "hold" in p and p.get("sound") != "continue"]
