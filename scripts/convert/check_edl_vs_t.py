"""Proves the edl port: (a) T's own inputs through vedit.cut.edl reproduce T's work/edl.json; (b) the fixture's edl vs T's.

    uv run python scripts/convert/check_edl_vs_t.py [--scratch DIR] [--fixture PATH] [--no-fixture]

Reads T read-only (constants through `ast`, no imports). T-side intermediates (the envelope) go under --scratch.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from t_cuts import FIXTURE, T_ROOT, constants, t_find

from vedit.cut import edl, signal
from vedit.cut.cutsfile import CutsFile, WordCut, resolve
from vedit.words import norm

FRAME = 1 / 30
T_DURATION = 928.45  # T tools/timeline.py DURATIONS["A"]


def compare(mine: dict, theirs: dict, tol: float) -> dict:
    a, b = mine["pieces"], theirs["pieces"]
    n = min(len(a), len(b))
    din = [abs(a[i]["in"] - b[i]["in"]) for i in range(n)]
    dout = [abs(a[i]["out"] - b[i]["out"]) for i in range(n)]
    bad = [i for i in range(n) if din[i] > tol or dout[i] > tol]
    return {
        "pieces": (len(a), len(b)),
        "total": (mine["total"], theirs["total"]),
        "fade_start": (mine["fade_start"], theirs["fade_start"]),
        "max_din": max(din, default=0),
        "max_dout": max(dout, default=0),
        "bad": bad,
    }


def t_exact(t_root: Path, scratch: Path) -> dict:
    c = constants(t_root / "tools" / "cuts.py", {"PHRASES", "KEEP_FILLERS", "OVERRIDES", "HOLDS"})
    refined = json.loads((t_root / "work" / "refined.json").read_text())
    words = json.loads((t_root / "work" / "A.words.json").read_text())
    wbc = {"A": words}
    keep_t = [float(k.split("|")[1]) for k in c["KEEP_FILLERS"]]
    cuts: list[WordCut] = []
    ref: dict = {}
    for clip, near, phrase in c["PHRASES"]:
        i = t_find(words, near, phrase)
        if i is None:
            continue
        j = i + len([w for w in phrase.split() if norm(w)])
        tk = f"{clip}|{near}|{phrase}"
        wc = WordCut(
            clip, "phrase", phrase, "", i, j - 1, words[i]["t0"],
            words[j]["t0"] if j < len(words) else T_DURATION, c["OVERRIDES"].get(tk), f"{clip} {near}",
        )  # fmt: skip
        cuts.append(wc)
        if tk in refined:
            ref[wc.key] = refined[tk]
    fillers, _ = resolve(CutsFile(fillers=True), wbc, {"A": T_DURATION})
    for (
        f
    ) in fillers:  # `resolve` with no keep list: drop T's KEEP_FILLERS here (they are `keep:` in cuts.yaml)
        if any(abs(f.w0 - t) < 0.005 for t in keep_t):
            continue
        cuts.append(f)
        tk = f"A|{round(f.w0, 2)}|{f.label}"
        if tk in refined:
            ref[f.key] = refined[tk]
    npy = scratch / "T-A-envelope.npy"
    if not npy.is_file():
        scratch.mkdir(parents=True, exist_ok=True)
        np.save(npy, signal.envelope(t_root / "work" / "A-48k.wav"))
    db = np.load(npy)
    holds = [(h[0], h[1], h[2]) for h in c["HOLDS"]]
    mine, info = edl.build(cuts, ref, {"A": db}, wbc, {"A": T_DURATION}, None, holds, "last-word", None)
    theirs = json.loads((t_root / "work" / "edl.json").read_text())
    return {"mine": mine, "theirs": theirs, "info": info, "cmp": compare(mine, theirs, FRAME)}


def show(name: str, cmp: dict) -> None:
    print(
        f"{name}: pieces {cmp['pieces'][0]} vs T {cmp['pieces'][1]}; total {cmp['total'][0]} vs {cmp['total'][1]};"
        f" fade_start {cmp['fade_start'][0]} vs {cmp['fade_start'][1]}"
    )
    print(f"  max |din| {cmp['max_din']:.4f}  max |dout| {cmp['max_dout']:.4f}  (1 frame = {FRAME:.4f})")


def fixture(fx: Path, theirs: dict) -> None:
    subprocess.run(
        [sys.executable, "-m", "vedit", "cut", "--wait", "--edl-only", "--project", str(fx)], check=True
    )
    mine = json.loads((fx / ".vedit" / "edl" / "edl.json").read_text())
    cmp = compare(mine, theirs, 2 * FRAME)
    show("fixture", cmp)
    # pieces compared by source boundary, not index (the counts differ)
    tb = sorted(p["in"] for p in theirs["pieces"] if "hold" not in p)
    tb += sorted(p["out"] for p in theirs["pieces"] if "hold" not in p)
    tarr = np.array(sorted(set(tb)))
    off = []
    for p in mine["pieces"]:
        if "hold" in p:
            continue
        for k in ("in", "out"):
            d = float(np.abs(tarr - p[k]).min())
            if d > 2 * FRAME:
                off.append((p["clip"], k, p[k], round(d, 2)))
    print(f"  my boundaries with no T boundary within 2 frames: {len(off)} of {2 * len(mine['pieces'])}")
    for o in off[:40]:
        print(f"    {o[0]} {o[1]:>3} {o[2]:8.2f}  nearest T {o[3]}s away")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--scratch", type=Path, default=Path("/tmp/vedit-edl-check"))
    ap.add_argument("--t-root", type=Path, default=T_ROOT)
    ap.add_argument("--fixture", type=Path, default=FIXTURE)
    ap.add_argument("--no-fixture", action="store_true")
    a = ap.parse_args(argv)
    res = t_exact(a.t_root, a.scratch)
    show("T-exact", res["cmp"])
    print(f"  pieces over 1 frame: {len(res['cmp']['bad'])} {res['cmp']['bad'][:10]}")
    if not a.no_fixture:
        fixture(a.fixture, res["theirs"])
    return 0 if not res["cmp"]["bad"] and res["cmp"]["pieces"][0] == res["cmp"]["pieces"][1] else 1


if __name__ == "__main__":
    raise SystemExit(main())
