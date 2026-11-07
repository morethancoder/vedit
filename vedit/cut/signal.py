"""Loudness envelope and quiet points of a source WAV (ported from T tools/cuts.py and tools/refine.py)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf

HOP = 100  # envelope rows per second (10 ms)
SIL_DB = -34.0  # below this a 10 ms row is silence (T cuts.py)


def envelope_of(audio: np.ndarray, sr: int) -> np.ndarray:
    """dB per 10 ms of the channel mean."""
    m = audio.mean(1) if audio.ndim > 1 else audio
    hop = sr // HOP
    n = len(m) // hop
    rms = np.sqrt((m[: n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-9
    return 20 * np.log10(rms)


def envelope(wav: Path, cache: Path | None = None) -> np.ndarray:
    """Envelope of a WAV file; cached as .npy next to `cache` when given (keyed by the caller)."""
    if cache is not None and cache.is_file():
        return np.load(cache)
    a, sr = sf.read(str(wav), always_2d=True)
    db = envelope_of(a, sr)
    if cache is not None:
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.save(cache, db)
    return db


def quietest(db: np.ndarray, t: float, reach: float) -> float:
    """Time of the quietest 10 ms row within `reach` seconds of t."""
    i0, i1 = max(0, int((t - reach) * HOP)), min(len(db) - 1, int((t + reach) * HOP))
    return (i0 + int(np.argmin(db[i0 : i1 + 1]))) / HOP


def minima(db: np.ndarray, lo: float, hi: float, k: int = 5) -> list[float]:
    """Up to k quiet points in [lo, hi], at least 80 ms apart, quietest first (3-row smoothing)."""
    i0, i1 = max(0, int(lo * HOP)), min(len(db) - 1, int(hi * HOP))
    seg = np.convolve(db[i0 : i1 + 1], np.ones(3) / 3, mode="same")
    picked: list[float] = []
    for o in np.argsort(seg):
        t = (i0 + int(o)) / HOP
        if all(abs(t - p) >= 0.08 for p in picked):
            picked.append(t)
        if len(picked) == k:
            break
    return picked


def silences(db: np.ndarray, sil_db: float = SIL_DB) -> list[tuple[float, float]]:
    """(start, end) seconds of every run of rows below sil_db."""
    runs, start = [], None
    for i, q in enumerate(db < sil_db):
        if q and start is None:
            start = i
        if not q and start is not None:
            runs.append((start / HOP, i / HOP))
            start = None
    if start is not None:
        runs.append((start / HOP, len(db) / HOP))
    return runs
