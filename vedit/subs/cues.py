"""Cues from the program transcription (T's numbers: 84 chars, 6 s, split on gaps of 0.6 s)."""

from __future__ import annotations

MAX_CHARS, MAX_DUR, GAP = 84, 6.0, 0.6
MIN_DUR, TAIL, FLOOR = (
    0.8,
    0.04,
    0.2,
)  # a cue shows at least 0.8 s unless the next one starts first (minus a 40 ms gap)


def build(words: list[dict]) -> list[dict]:
    """`[{t0, t1, w}]` in program time -> `[{id, t0, t1, text}]`, ids from 1."""
    out: list[dict] = []
    cur: list[dict] = []
    for i, w in enumerate(words):
        if not str(w.get("w", "")).strip():
            continue
        cur.append(w)
        text = " ".join(x["w"] for x in cur)
        nxt = next((x for x in words[i + 1 :] if str(x.get("w", "")).strip()), None)
        stop = (
            nxt is None
            or nxt["t0"] - w["t1"] > GAP
            or (w["w"][-1] in ".?!" and len(text) > 30)
            or len(text) + 1 + len(nxt["w"]) > MAX_CHARS
            or nxt["t1"] - cur[0]["t0"] > MAX_DUR
        )
        if stop:
            out.append({"t0": round(cur[0]["t0"], 2), "t1": round(w["t1"], 2), "text": text})
            cur = []
    for i, c in enumerate(out):
        c["id"] = i + 1
        nxt = out[i + 1]["t0"] if i + 1 < len(out) else c["t1"] + 1
        # ASR words can overlap the next cue; never let a cue end before it starts.
        c["t1"] = round(max(min(max(c["t1"], c["t0"] + MIN_DUR), nxt - TAIL), c["t0"] + FLOOR), 2)
    return out
