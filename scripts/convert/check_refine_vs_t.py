"""Check vedit's refine (vedit/cut/refine.py) against T's hand-run work/refined.json on the Telegram fixture.

Loads ~/Demos/vedit-fixture-tele, resolves cuts.yaml against its words, runs refine.run for real (Studio must be
running; writes the fixture's .vedit/edl/refined.json), then matches each refined cut to a T entry by time overlap
and reports how far in/out differ. T is only read.

    uv run python scripts/convert/check_refine_vs_t.py [--t ~/Demos/tele-a7-growth-story] [--fixture ...]
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path

import soundfile as sf

from vedit.cut import cutsfile, refine
from vedit.project import Project
from vedit.words.model import load

FRAME = 0.034


def match(cut_in: float, cut_out: float, t_entries: list[dict]) -> dict | None:
    """The T entry whose [in, out] overlaps ours most (ties: nearest start)."""
    best, best_key = None, None
    for t in t_entries:
        ov = min(cut_out, t["out"]) - max(cut_in, t["in"])
        if ov < -0.3:  # allow near-touching ranges (zero-width cuts)
            continue
        key = (-ov, abs(cut_in - t["in"]))
        if best_key is None or key < best_key:
            best, best_key = t, key
    return best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--t", default="~/Demos/tele-a7-growth-story")
    ap.add_argument("--fixture", default="~/Demos/vedit-fixture-tele")
    a = ap.parse_args()
    t_root, fx = Path(a.t).expanduser(), Path(a.fixture).expanduser()
    project = Project.load(fx)
    paths = project.paths
    clips = list(project.sources)
    words = {c: load(paths, c) for c in clips}
    durations = {c: sf.info(str(paths.media / f"{c}-48k.wav")).duration for c in clips}
    cf = cutsfile.load(paths.cuts)
    cuts, problems = cutsfile.resolve(cf, words, durations)
    print(f"{len(cuts)} cuts resolved, {len(problems)} problems")

    t0 = time.time()
    res = refine.run(
        project, paths, cuts, words, log=print, progress=lambda d, n: print(f"  {d}/{n}", flush=True)
    )
    dt = time.time() - t0
    print(
        f"refine: listened {res.listened}, cached {res.cached}, {res.splices} splices, "
        f"{res.minutes:.1f} min of audio, {dt:.0f} s"
    )
    t_ref = json.loads((t_root / "work" / "refined.json").read_text())
    by_clip: dict[str, list[dict]] = {}
    for k, v in t_ref.items():
        by_clip.setdefault(k.split("|")[0], []).append({**v, "key": k})
    rows = []
    for c in cuts:
        r = res.get(c.key)
        if r is None:
            continue
        m = match(r["in"], r["out"], by_clip.get(c.clip, []))
        if m:
            rows.append((c, r, m))
    print(f"matched {len(rows)} of {len(res)} refined cuts to T entries ({len(t_ref)} in T)")
    if not rows:
        return
    di = [abs(r["in"] - m["in"]) for _, r, m in rows]
    do = [abs(r["out"] - m["out"]) for _, r, m in rows]
    n = len(rows)
    for name, d in (("in", di), ("out", do)):
        print(
            f"|d{name}|: median {statistics.median(d):.3f} max {max(d):.3f} "
            f"within 1 frame {sum(x <= FRAME for x in d)}/{n} within 0.1 s {sum(x <= 0.1 for x in d)}/{n}"
        )
    both = [max(x, y) for x, y in zip(di, do, strict=True)]
    print(
        f"both within 1 frame {sum(x <= FRAME for x in both)}/{n}, within 0.1 s {sum(x <= 0.1 for x in both)}/{n}"
    )
    print("worst 10:")
    for i in sorted(range(n), key=lambda i: -both[i])[:10]:
        c, r, m = rows[i]
        print(
            f"  {c.clip} {c.label[:30]!r}: ours {r['in']:.2f}-{r['out']:.2f} T {m['in']:.2f}-{m['out']:.2f}"
        )
        print(f"     ours heard: {r['heard']}")
        print(f"     T    heard: {m['heard']}")


if __name__ == "__main__":
    main()
