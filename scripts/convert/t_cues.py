"""One-off: convert the Telegram video's hand-made cues (T tools/build.py CUES + CHAPTERS) into a vedit cues.yaml.

T and the fixture have different transcriptions of the same audio on the same source timeline, so the
conversion goes by TIME: a T cue's start/end/beat times pick the fixture words spoken there, and those words
become `at` / `until` / beats (each checked to resolve to exactly those words). Reads T only through `ast`
(`YELLOW` is substituted); never writes in T. Copies T's ptb favicon to the fixture's custom/logos/ptb.svg.

    uv run python scripts/convert/t_cues.py [--out ~/Demos/vedit-fixture-tele/cues.yaml]
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import json
import shutil
import statistics
import sys
from pathlib import Path

from vedit.cut.cutsfile import load as load_cuts
from vedit.graphics import cues as cue_mod
from vedit.graphics.anchors import first_after, kept, words_kept
from vedit.project import Project
from vedit.report import VeditError
from vedit.words import Edl, find, norm, tokens

T_ROOT = Path("~/Demos/tele-a7-growth-story").expanduser()
FIXTURE = Path("~/Demos/vedit-fixture-tele").expanduser()
YELLOW = "accent"  # T's yellow was its accent: follow the style
HEADER = "# cues.yaml: graphics anchored to spoken words. `vedit guide cues`.\n# Converted from T tools/build.py CUES by scripts/convert/t_cues.py (times -> fixture words).\n"
TYPE_OF = {"big": "big-number", "ptb": "plug"}


def t_constants(py: Path, names: set[str]) -> dict:
    """Top-level `NAME = <literal>` of a file via ast; the Name YELLOW is replaced by its colour."""

    class Sub(ast.NodeTransformer):
        def visit_Name(self, node):
            return ast.Constant(YELLOW) if node.id == "YELLOW" else node

    out = {}
    for node in ast.parse(py.read_text()).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Tuple):  # A, B = 1, 2
            for t, v in zip(node.targets[0].elts, node.value.elts, strict=True):
                if isinstance(t, ast.Name) and t.id in names:
                    out[t.id] = ast.literal_eval(v)
        elif (
            isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
        ) and node.targets[0].id in names:
            out[node.targets[0].id] = ast.literal_eval(ast.fix_missing_locations(Sub().visit(node.value)))
    return out


def t_find(words, phrase, near, reach):
    """T build.py `_find_words`: start index of the exact normalised phrase nearest `near` within reach."""
    want = [norm(w) for w in phrase.split() if norm(w)]
    best = None
    for i in range(len(words) - len(want) + 1):
        if [norm(w["w"]) for w in words[i : i + len(want)]] == want and abs(words[i]["t0"] - near) < reach:
            d = abs(words[i]["t0"] - near)
            if best is None or d < best[0]:
                best = (d, i)
    return None if best is None else best[1]


def nearest(fw, t, key="t0", k=16, edl=None):
    """Indices of the words whose `key` time is nearest t (words with letters; kept ones when an edl is given)."""
    ok = [i for i, w in enumerate(fw) if tokens(w["w"]) and (edl is None or kept(edl, "A", w["t0"], w["t1"]))]
    return sorted(ok, key=lambda i: abs(fw[i][key] - t))[:k]


def at_words(fw, fwb, t, edl):
    """2-5 fixture words starting nearest t that `find` resolves to exactly them: (phrase, near, index)."""
    for i in nearest(fw, t, edl=edl):
        for n in range(2, 6):
            if i + n > len(fw):
                break
            near = f"A {fw[i]['t0']:g}"
            phrase = " ".join(w["w"] for w in fw[i : i + n])
            try:
                s = find(fwb, phrase, near)
            except VeditError:
                continue
            if s.i0 == i and words_kept(edl, "A", fw, s.i0, s.i1):
                return phrase, near, i
    return None


def until_words(fw, t1, i_at, t_at, edl, max_dev=1.0):
    """2-4 fixture words ending nearest t1 that are the first match after the anchor: (phrase, last index)."""
    for j in nearest(fw, t1, "t1", edl=edl):
        for n in range(2, 5):
            i = j - n + 1
            if i <= i_at:
                continue
            phrase = " ".join(w["w"] for w in fw[i : j + 1])
            s = first_after(fw, phrase, "A", t_at, t_at + cue_mod.FORWARD)
            if abs(fw[j]["t1"] - t1) > max_dev:
                return None  # candidates are nearest first: nothing closer follows
            if s is not None and s.i0 == i and words_kept(edl, "A", fw, s.i0, s.i1):
                return phrase, j
    return None


def phrase_at(fw, t, lo, hi, edl, ns=(2, 3, 1, 4)):
    """Fixture words spoken nearest t that are the FIRST match inside [lo, hi] (the loader's beat rule)."""
    for i in nearest(fw, t, edl=edl):
        for n in ns:
            if i + n > len(fw) or not lo <= fw[i]["t0"] <= hi:
                continue
            phrase = " ".join(w["w"] for w in fw[i : i + n])
            s = first_after(fw, phrase, "A", lo, hi)
            if s is not None and s.i0 == i:
                return phrase
    return None


def q(s) -> str:
    return json.dumps(s, ensure_ascii=False)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=FIXTURE / "cues.yaml")
    ap.add_argument("--t-root", type=Path, default=T_ROOT)
    ap.add_argument("--fixture", type=Path, default=FIXTURE)
    a = ap.parse_args(argv)

    c = t_constants(a.t_root / "tools" / "build.py", {"CUES", "CHAPTERS", "PTB_URL_AT", "PTB_FREE_AT"})
    tw = json.loads((a.t_root / "work" / "A.words.json").read_text())
    fw = json.loads((a.fixture / ".vedit" / "words" / "A.json").read_text())
    fwb = {"A": fw}
    edl = Edl.load(a.fixture / ".vedit" / "edl" / "edl.json")
    out, issues, meta = [HEADER, "cues:"], [], []

    for kind, cid, clip, t0, t1, f in c["CUES"]:
        typ = TYPE_OF.get(kind, kind)
        t_at = t0
        if kind == "kinetic":  # anchored on the words the speaker says, not the line shown
            i = t_find(tw, f["heard"], t0, (t1 - t0) + 3)
            t_at = tw[i]["t0"] if i is not None else t0
        anchor = at_words(fw, fwb, t_at, edl)
        if anchor is None:
            issues.append(f"{cid}: no fixture words resolve near {t_at}")
            continue
        phrase, near, i_at = anchor
        lines = [f"  - type: {typ}", f"    id: {cid}", f"    at: {q(phrase)}", f"    near: {near}"]
        end_src = None
        if kind != "kinetic":
            if t1 == "end":
                lines.append("    until: end")
            else:
                u = until_words(fw, t1, i_at, fw[i_at]["t0"], edl)
                if u:
                    lines.append(f"    until: {q(u[0])}")
                else:
                    lines.append(f"    for: {round(edl.g('A', t1) - edl.g('A', fw[i_at]['t0']), 2):g}")
                    issues.append(f"{cid}: no until words within 1 s of {t1}, wrote for:")
            end_src = t1
        if kind == "label":
            lines += [f"    {k}: {q(f[k])}" for k in ("logo", "kicker", "title", "sub") if k in f]
        elif kind == "chip":
            lines += [f"    {k}: {q(f[k])}" for k in ("label", "code")]
        elif kind == "big":
            lines += [f"    {k}: {q(f[k])}" for k in ("pre", "word", "color") if k in f]
        elif kind == "kinetic":
            lines += [
                f"    words: {q(f['words'])}",
                "    highlight: [" + ", ".join(q(x) for x in f["hl"]) + "]",
            ]
        elif kind == "doodle":
            lines += [f"    scene: {f['doodle']}", "    beats:"]
            lo = fw[i_at]["t0"] - cue_mod.LEAD
            hi = (
                (t1 if t1 != "end" else lo + cue_mod.FORWARD) + 5 + 5
            )  # span + 5 s, plus a margin for the until words
            for el, (bclip, bnear, bphrase) in f["beats"].items():
                k = t_find(tw, bphrase, bnear, 3)
                tb = tw[k]["t0"] if k is not None else bnear
                p = phrase_at(fw, tb, lo, hi, edl)
                if p is None:
                    issues.append(f"{cid}: beat {el!r} at {tb}: no fixture words")
                    continue
                lines.append(f"      {q(el)}: {q(p)}")  # quoted: YAML reads bare no/on as booleans
        elif kind == "ptb":
            for slot, tt in (("url", c["PTB_URL_AT"]), ("trial", c["PTB_FREE_AT"])):
                p = phrase_at(fw, tt, fw[i_at]["t0"] - cue_mod.LEAD, t1 + 5 + 5, edl)
                if p:
                    lines.append(f"    {slot}: {q(p)}")
                else:
                    issues.append(f"{cid}: slot {slot} at {tt}: no fixture words")
        out += lines
        meta.append((cid, typ, t_at, end_src))
    a.out.write_text("\n".join(out) + "\n")

    logo = a.fixture / "custom" / "logos" / "ptb.svg"
    logo.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(a.t_root / "hf" / "assets" / "ptb" / "favicon.svg", logo)

    cf = load_cuts(a.fixture / "cuts.yaml")
    same = [
        (ch.title, ch.kicker, ch.logo) == (t["title"], t["kicker"], t["logo"])
        for ch, t in zip(cf.chapters, c["CHAPTERS"], strict=False)
    ]
    print(f"wrote {a.out}: {len(meta)} of {len(c['CUES'])} T cues")
    print(
        f"cuts.yaml chapters vs T CHAPTERS: {len(cf.chapters)} vs {len(c['CHAPTERS'])}, all equal: {all(same) and len(same) == len(c['CHAPTERS'])}"
    )
    for s in issues:
        print("  ISSUE", s)

    # check: load with the real loader on the fixture (the yellow-doodle pack is phase 05: use the base pack)
    proj = dataclasses.replace(Project.load(a.fixture), style=None)
    try:
        loaded = cue_mod.load(proj, proj.paths, edl, fwb)
    except VeditError as e:
        print("LOAD FAILED\n", e)
        return 1
    chs = cue_mod.chapters(
        cf, edl, logos={**cue_mod.packs.load("base").logos(), **cue_mod.custom_logos(proj.paths)}
    )
    print(f"loaded {len(loaded)} cues + {len(chs)} chapters")
    ds, de, bad = [], [], 0
    by = {m[0]: m for m in meta}
    for cue in loaded:
        _, _, t0, t1 = by[cue.id]
        s_dev = cue.src - t0
        ds.append(abs(s_dev))
        e_src = edl.src(max(cue.end - 0.001, 0))[1]
        e_dev = None if t1 in (None, "end") else e_src - t1
        if e_dev is not None:
            de.append(abs(e_dev))
        flag = f"  PROBLEMS {cue.problems}" if cue.problems else ""
        bad += bool(cue.problems)
        print(
            f"  {cue.id:14s} {cue.type:10s} start {s_dev:+.2f}  end {'' if e_dev is None else f'{e_dev:+.2f}'}{flag}"
        )
    print(f"start deviation vs T (source s): max {max(ds):.2f} median {statistics.median(ds):.2f}")
    print(
        f"end deviation vs T (source s):   max {max(de):.2f} median {statistics.median(de):.2f} (n={len(de)})"
    )
    print(f"cues with problems: {bad}")
    return 0 if not issues and not bad else 1


if __name__ == "__main__":
    sys.exit(main())
