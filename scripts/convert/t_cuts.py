"""One-off: convert the Telegram video's hand-made cuts (T tools/cuts.py) into a vedit cuts.yaml.

T and the fixture have different transcriptions of the same audio, so the conversion goes by TIME: each T
phrase is found in T's words (T's own `find`: exact normalised match, start within 6 s of `near`), and the
fixture words inside that cut range become `say:`. Reads T only through `ast` + literal_eval (no imports).

    uv run python scripts/convert/t_cuts.py [--out ~/Demos/vedit-fixture-tele/cuts.yaml]
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

import soundfile as sf

from vedit.cut.cutsfile import FILLERS, load, resolve
from vedit.report import VeditError
from vedit.words import AmbiguousMatch, norm

T_ROOT = Path("~/Demos/tele-a7-growth-story").expanduser()
FIXTURE = Path("~/Demos/vedit-fixture-tele").expanduser()
LONG_WORDS = 12  # phrases longer than this are written as from/to
HEADER_DEFAULT = """\
# cuts.yaml: what to remove or mark. Written by you after reading the transcript. `vedit guide cuts`.
"""


def constants(py: Path, names: set[str]) -> dict:
    """Top-level `NAME = <literal>` assignments of a Python file, without importing it."""
    out = {}
    for node in ast.parse(py.read_text()).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            t = node.targets[0]
            if isinstance(t, ast.Name) and t.id in names:
                if isinstance(node.value, ast.Call):  # FILLERS = re.compile(...) is not a literal
                    continue
                out[t.id] = ast.literal_eval(node.value)
    return out


def t_find(words, near, phrase):
    """T cuts.py `find`."""
    want = [norm(w) for w in phrase.split() if norm(w)]
    best = None
    for i in range(len(words) - len(want) + 1):
        if [norm(w["w"]) for w in words[i : i + len(want)]] == want:
            d = abs(words[i]["t0"] - near)
            if d < 6 and (best is None or d < best[0]):
                best = (d, i)
    return None if best is None else best[1]


def inside(words, a, b):
    """Indices of words whose middle falls in [a, b)."""
    return [i for i, w in enumerate(words) if a <= (w["t0"] + w["t1"]) / 2 < b]


def runs(idx):
    """The longest run of consecutive word indices (the fixture words are not strictly in time order)."""
    best, cur = [], []
    for i in idx:
        cur = cur + [i] if cur and i == cur[-1] + 1 else [i]
        if len(cur) > len(best):
            best = cur
    return best


def q(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def num(x: float) -> str:
    return f"{x:g}"


def header(out: Path) -> str:
    if out.exists():
        head = []
        for line in out.read_text().splitlines():
            if not line.startswith("#"):
                break
            head.append(line)
        if head:
            return "\n".join(head) + "\n"
    return HEADER_DEFAULT


def make_item(fw, idx, window_hint, dur_clip):
    """Cut item for the fixture words idx; sets `window:` only where find needs it."""
    near = f"A {fw[idx[0]]['t0']:g}"
    text = " ".join(fw[i]["w"] for i in idx)
    item = {"near": near, "say": text}
    if len(idx) > LONG_WORDS:
        span = fw[idx[-1]]["t1"] - fw[idx[0]]["t0"]
        item = {
            "near": near,
            "from": " ".join(fw[i]["w"] for i in idx[:3]),
            "to": " ".join(fw[i]["w"] for i in idx[-3:]),
            "window": round(span + 6, 1),
        }
    return item


def verified(item, fw_by_clip, idx):
    """Make `item` resolve to exactly the intended word span; narrow `window` for ambiguity."""
    for win in (None, 0.5, 0.3, 0.1):
        it = dict(item)
        if win and "window" not in it:
            it["window"] = win
        from vedit.cut.cutsfile import Cut, _resolve_cut

        c = Cut(it["near"], it.get("say"), it.get("from"), it.get("to"), "", it.get("window"))
        try:
            _, i0, i1, _ = _resolve_cut(c, fw_by_clip, {})
        except AmbiguousMatch:
            continue
        except VeditError:
            return None
        if (i0, i1) == (idx[0], idx[-1]):
            return it
    return None


def line(it: dict) -> str:
    parts = [f"near: {it['near']}"]
    for k in ("say", "from", "to"):
        if k in it:
            parts.append(f"{k}: {q(it[k])}")
    if "window" in it:
        parts.append(f"window: {num(it['window'])}")
    if it.get("why"):
        parts.append(f"why: {it['why']}")
    return "  - {" + ", ".join(parts) + "}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=FIXTURE / "cuts.yaml")
    ap.add_argument("--t-root", type=Path, default=T_ROOT)
    ap.add_argument("--fixture", type=Path, default=FIXTURE)
    a = ap.parse_args(argv)

    c = constants(a.t_root / "tools" / "cuts.py", {"PHRASES", "KEEP_FILLERS", "OVERRIDES", "HOLDS"})
    chapters = constants(a.t_root / "tools" / "build.py", {"CHAPTERS"})["CHAPTERS"]
    refined = json.loads((a.t_root / "work" / "refined.json").read_text())
    tw = json.loads((a.t_root / "work" / "A.words.json").read_text())
    fw = json.loads((a.fixture / ".vedit" / "words" / "A.json").read_text())
    fwb = {"A": fw}
    dur = {"A": sf.info(str(next((a.fixture / ".vedit" / "media").glob("A-48k.wav")))).duration}

    items, differs, issues = [], [], []
    for clip, near, phrase in c["PHRASES"]:
        okey = f"{clip}|{near}|{phrase}"
        pin = c["OVERRIDES"].get(okey)
        i = t_find(tw, near, phrase)
        if i is None:
            issues.append(f"T MISS {near} {phrase!r}")
            continue
        n = len([w for w in phrase.split() if norm(w)])
        j = i + n
        t0 = tw[i]["t0"]
        t1 = tw[j]["t0"] if j < len(tw) else dur[clip]
        # the range T really cut: pinned by ear, else the listened (refined) boundaries, else its word times
        r = refined.get(okey)
        if pin:
            t0, t1 = pin
        elif r:
            t0, t1 = r["in"], r["out"]
        idx = runs(inside(fw, t0, t1))
        # T's own words exactly present near that range (padded 1 s for timing drift): cut just those
        want = [norm(w) for w in phrase.split() if norm(w)]
        pad = inside(fw, t0 - 1.0, t1 + 1.0)
        hits = [
            pad[k : k + len(want)]
            for k in range(len(pad) - len(want) + 1)
            if pad[k + len(want) - 1] - pad[k] == len(want) - 1
            and [norm(fw[i]["w"]) for i in pad[k : k + len(want)]] == want
        ]
        if hits:
            idx = min(hits, key=lambda h: abs(fw[h[0]]["t0"] - t0))
        if not idx:  # the fixture transcript has no word there: cut by seconds
            items.append({"near": f"A {near:g}", "pin": (t0, t1), "pin_only": True, "tphrase": phrase})
            continue
        it = verified(make_item(fw, idx, None, dur), fwb, idx)
        if it is None:
            issues.append(f"cannot address fixture words {fw[idx[0]]['t0']} for T {phrase!r}")
            continue
        it["pin"], it["tphrase"] = pin, phrase
        ftext = " ".join(fw[k]["w"] for k in idx)
        if [norm(w) for w in phrase.split() if norm(w)] != [norm(w) for w in ftext.split() if norm(w)]:
            differs.append(f"{near:7.2f}  T: {phrase}  ->  fixture: {ftext}")
        items.append(it)

    keeps = []
    for k in sorted(c["KEEP_FILLERS"]):
        _, t = k.split("|")
        t = float(t)
        w = next((w for w in tw if abs(w["t0"] - t) < 0.01), None)
        idx = [min(range(len(fw)), key=lambda i: abs(fw[i]["t0"] - t))]
        if not w or abs(fw[idx[0]]["t0"] - t) > 0.3:
            issues.append(f"KEEP {k}: no fixture word there")
            continue
        keeps.append({"near": f"A {t:g}", "say": " ".join(fw[i]["w"] for i in idx), "tword": w["w"]})

    out = [header(a.out), "pauses: { max: 0.5, keep: 0.3 }", "fillers: true", "cuts:"]
    pins = []
    for it in items:
        if it.get("pin_only"):
            pins.append({"near": it["near"], "in": it["pin"][0], "out": it["pin"][1]})
            out.append(
                f"  # T {it['tphrase']!r} at {it['near'][2:]}: no word in this transcript, cut by seconds: see pins"
            )
            continue
        out.append(line(it))
        if it["pin"]:
            pins.append({"near": it["near"], "in": it["pin"][0], "out": it["pin"][1]})
    out.append("keep:")
    out += ["  - {" + f"near: {k['near']}, say: {q(k['say'])}" + "}  # T: " + k["tword"] for k in keeps]
    out.append("pins:")
    out += ["  - {" + f"near: {p['near']}, in: {num(p['in'])}, out: {num(p['out'])}" + "}" for p in pins]
    out.append("chapters:")
    for (clip, t, _hold), ch in zip(c["HOLDS"], chapters, strict=True):
        parts = [f"near: {clip} {t:g}", f"title: {q(ch['title'])}"]
        parts += [f"{k}: {q(ch[k])}" for k in ("kicker", "logo") if k in ch]
        out.append("  - {" + ", ".join(parts) + "}")
    out.append("end: last-word")
    a.out.write_text("\n".join(out) + "\n")

    cf = load(a.out)
    cuts, problems = resolve(cf, fwb, dur)
    kinds = {k: sum(1 for x in cuts if x.kind == k) for k in ("phrase", "filler", "pin")}
    tfill = [
        (w["t0"], w["w"])
        for w in tw
        if FILLERS.match(norm(w["w"])) and f"A|{round(w['t0'], 2)}" not in c["KEEP_FILLERS"]
    ]
    ffill = [(x.w0, x.label) for x in cuts if x.kind == "filler"]
    print(f"wrote {a.out}")
    print(
        f"T phrases {len(c['PHRASES'])} -> cuts in file {len(cf.cuts)}, pins {len(cf.pins)}, keep {len(cf.keep)}"
    )
    print(
        f"resolved {len(cuts)} ({kinds}); pins attached {sum(1 for x in cuts if x.pin)}; problems {len(problems)}"
    )
    for p in problems:
        print("  PROBLEM", p["section"], p["cut"], p["near"], p["text"], "->", p["error"].splitlines()[0])
    for s in issues:
        print("  ISSUE", s)
    print(f"fillers cut: T {len(tfill)} {tfill}")
    print(f"fillers cut: fixture {len(ffill)} {ffill}")
    print(f"phrases whose text differs ({len(differs)}):")
    print("\n".join(differs))
    return 0 if not problems and not issues else 1


if __name__ == "__main__":
    sys.exit(main())
