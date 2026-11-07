"""Listen to excerpts: stitch audio pieces with silent gaps, transcribe them in ONE Studio pass, hand back the
heard words per piece. Shared by `vedit listen`, boundary refinement and join checks.

    audio, sr = read_wav(wav)                           # mono float32
    pieces = [cut(audio, sr, 300, 312), splice_piece(audio, sr, 668.78, 672.2)]
    heard = listen(project, pieces, sr, name="probe")   # heard[i] = words of pieces[i], times local to piece i

Gaps keep the ASR from running a sentence across two pieces (docs/traps.md): 2 s for probes, 2.5 s for program
reads. Studio caches by content, so listening to the same pieces again is free.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from vedit import studio
from vedit.project import Project
from vedit.run import log_path

GAP = 2.0  # silence between pieces (probe, stamps)
PROGRAM_GAP = 2.5  # pprobe
SPLICE_SIDE = 1.8  # seconds kept before `in` and after `out` of a candidate splice
PROGRAM_SIDE = 2.2  # seconds either side of a program time


@dataclass
class Heard:
    """One word the ASR heard; times are seconds from the start of its excerpt."""

    start: float
    end: float
    text: str

    @property
    def mid(self) -> float:
        return (self.start + self.end) / 2


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    """WAV as mono float32 (channels averaged) and its sample rate."""
    a, sr = sf.read(str(path), dtype="float32", always_2d=True)
    return a.mean(axis=1), int(sr)


def cut(audio: np.ndarray, sr: int, s: float, e: float) -> np.ndarray:
    """Samples of [s, e) seconds, clamped to the audio."""
    i0 = max(0, round(s * sr))
    i1 = min(len(audio), max(i0, round(e * sr)))
    return audio[i0:i1]


def splice_piece(audio: np.ndarray, sr: int, s: float, e: float, side: float = SPLICE_SIDE) -> np.ndarray:
    """The candidate join "cut from `s` to `e`": `side` s before `s` followed by `side` s after `e`."""
    return np.concatenate([cut(audio, sr, s - side, s), cut(audio, sr, e, e + side)])


def stitch(
    pieces: list[np.ndarray], sr: int, gap: float = GAP
) -> tuple[np.ndarray, list[tuple[float, float]]]:
    """Join pieces with `gap` s of silence after each. Returns the audio and each piece's (t0, t1) in it."""
    parts, spans, t = [], [], 0.0
    silence = np.zeros(round(gap * sr), dtype=np.float32)
    for p in pieces:
        d = len(p) / sr
        spans.append((t, t + d))
        parts += [np.asarray(p, dtype=np.float32), silence]
        t += d + gap
    return (np.concatenate(parts) if parts else np.zeros(0, np.float32)), spans


def assign(words: list[studio.Word], spans: list[tuple[float, float]]) -> list[list[Heard]]:
    """Give each heard word to the piece whose span holds its mid-time; times become local to that piece."""
    out: list[list[Heard]] = [[] for _ in spans]
    for w in words:
        mid = (w.start + w.end) / 2
        for i, (t0, t1) in enumerate(spans):
            if t0 <= mid <= t1:
                out[i].append(Heard(w.start - t0, w.end - t0, w.text))
                break
    return out


def listen(
    project: Project, pieces: list[np.ndarray], sr: int, *, name: str = "listen", gap: float = GAP
) -> list[list[Heard]]:
    """Stitch `pieces` into `.vedit/listen/<name>.wav`, transcribe once, return the words heard per piece."""
    if not pieces:
        return []
    paths = project.paths
    audio, spans = stitch(pieces, sr, gap)
    wav = paths.vedit / "listen" / f"{name}.wav"
    wav.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(wav), audio, sr)
    t = studio.transcribe(
        wav,
        project.lang,
        project.dialect,
        project.hint,
        fillers="keep",
        vad=False,
        cache_dir=paths.studio,
        log=log_path(paths.root, "listen"),
    )
    return assign(t.words, spans)
