"""Find the joins that sound wrong: transcribe the cut program, compare the words heard around each join with
the words the cut should have left (source words minus what the edl removed). Port of T tools/joins.py plus
the comparison T did by eye (docs/pipeline.md `## joins`).

    words = program_words(project, edl)                  # Studio on program.wav -> [{t0, t1, w, clip, st}]
    joins = check(edl, source_words, words)              # one dict per join; "flags" is empty when it reads fine

Plain code only: tokens are normalised (Arabic-aware, vedit.words.norm), matched fuzzily so ASR spelling
variants (تيليغرام / تلغرام) agree, then only what happens within ZONE seconds of the join is judged.
"""

from __future__ import annotations

import difflib
import itertools
import json
import re

from vedit import studio
from vedit.run import hash_of, log_path, sample_hash
from vedit.words.norm import norm
from vedit.words.timeline import Edl

SIDE = 2.2  # seconds of program read before and after a join (T joins.py)
ZONE = 1.0  # only words this close to the join are judged; the rest anchor the alignment
MATCH = 0.8  # token similarity that counts as the same word
NEAR = 0.6  # similarity of an unmatched pair that counts as a garbled version of the expected word
FILLERS = re.compile(r"^(ا{2,}|ام+|اه+|ها+|هم+|um+|uh+|uhm|erm|ah+|يعني)$")
NEGATIONS = {
    "ما",
    "مو",
    "لا",
    "مش",
    "ماكو",
    "مب",
    "ليس",
    "لم",
    "لن",
    "no",
    "not",
    "never",
    "dont",
    "cant",
    "wont",
}
NUMBERS = {
    "واحد",
    "اثنين",
    "ثلاثه",
    "اربعه",
    "خمسه",
    "عشره",
    "مليون",
    "الف",
    "ميه",
    "مايه",
    "مئه",
    "اثنا",
    "عشر",
    "ستين",
}
CUT_BAND = 0.1  # a removed word counts as surely removed this far inside the cut
BAND = 0.35  # seconds either side of a piece edge where word times cannot be trusted
_FOLD = str.maketrans(
    {
        "ث": "ت",
        "ط": "ت",
        "ذ": "ت",
        "ظ": "ت",
        "ض": "ت",
        "د": "ت",
        "ص": "س",
        "غ": "ج",
        "ع": "ا",
        "ء": "ا",
        "ة": "ه",
    }
)
_DROP = re.compile(r"(?<=.)[اويه]")  # vowel letters after the first letter


def meaning(tok: str) -> bool:
    """Negations and numbers: dropping one flips or changes the sentence."""
    return tok in NEGATIONS or tok in NUMBERS or any(c.isdigit() for c in tok)


def _base(tok: str) -> str:
    return tok[2:] if len(tok) > 4 and tok.startswith("ال") else tok


def skeleton(tok: str) -> str:
    return _DROP.sub("", re.sub(r"(.)\1+", r"\1", _base(tok).translate(_FOLD)))


def sim(a: str, b: str) -> float:
    """Similarity of two normalised tokens in 0..1; spelling variants of one word score high."""
    if a == b:
        return 1.0
    a, b = _base(a), _base(b)
    if a == b:
        return 1.0
    if min(len(a), len(b)) <= 2:
        return 0.0  # short words (ما, لا, في) match exactly or not at all
    if a.isdigit() != b.isdigit() and (a in NUMBERS or b in NUMBERS):
        return 1.0  # "2" and اثنين are the same number
    if a.translate(_FOLD) == b.translate(_FOLD):
        return 0.95  # same letters up to look-alike consonants (عضو / أضو, البوت / البود)
    plain = difflib.SequenceMatcher(None, a, b).ratio()
    sa, sb = skeleton(a), skeleton(b)
    if min(len(sa), len(sb)) < 3:
        return plain
    return 0.95 if sa == sb else max(plain, difflib.SequenceMatcher(None, sa, sb).ratio() * 0.95)


def is_fragment(heard: str, expected: str) -> bool:
    """`heard` is a clipped piece of `expected` (يك of يكون)."""
    h, e = _base(heard), _base(expected)
    return 1 <= len(h) < len(e) and (e.startswith(h) or e.endswith(h))


def _tok(w: str) -> str | None:
    k = norm(w)
    return k if k and not FILLERS.match(k) else None


def align(exp: list[str], heard: list[str]) -> list[tuple[int | None, int | None]]:
    """Order-preserving alignment (global DP, fuzzy token match); pairs (i, j), None where one side has a gap."""
    n, m = len(exp), len(heard)
    best = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            s = sim(exp[i], heard[j])
            best[i][j] = max(best[i + 1][j], best[i][j + 1], best[i + 1][j + 1] + (s if s >= MATCH else -1))
    out, i, j = [], 0, 0
    while i < n and j < m:
        s = sim(exp[i], heard[j])
        if s >= MATCH and abs(best[i][j] - (best[i + 1][j + 1] + s)) < 1e-9:
            out.append((i, j))
            i, j = i + 1, j + 1
        elif best[i + 1][j] >= best[i][j + 1]:
            out.append((i, None))
            i += 1
        else:
            out.append((None, j))
            j += 1
    out += [(k, None) for k in range(i, n)] + [(None, k) for k in range(j, m)]
    return out


def _gaps(pairs):
    """Runs of unmatched tokens between matched anchors: (expected indices, heard indices)."""
    e, h = [], []
    for i, j in pairs:
        if i is not None and j is not None:
            if e or h:
                yield e, h
            e, h = [], []
        else:
            if i is not None:
                e.append(i)
            if j is not None:
                h.append(j)
    if e or h:
        yield e, h


def compare(exp: list[tuple], heard: list[tuple[str, float]], removed: list[str], t: float) -> list[dict]:
    """Flags for one join at program time `t`.

    exp: (token, program mid-time, sure); `sure` is False for words within BAND s of a piece edge, where ASR word
    times (drift up to ~0.5 s) cannot say whether the cut kept them: they may pair with a heard fragment but are
    never reported missing. heard: (token, program mid-time). removed: tokens the cut surely took.
    """
    et, ht = [x[0] for x in exp], [x[0] for x in heard]
    flags = []
    near = lambda x: abs(x - t) <= ZONE
    keep = set(et)
    for ei, hi in _gaps(align(et, ht)):
        ez = [i for i in ei if near(exp[i][1])]
        hz = [j for j in hi if near(heard[j][1])]
        used, hit = set(), set()
        for i in ez:
            e = et[i]
            pair = max((j for j in hz if j not in used), key=lambda j: sim(e, ht[j]), default=None)
            if pair is not None and is_fragment(ht[pair], e):
                flags.append({"kind": "clipped", "expected": e, "heard": ht[pair]})
            elif pair is not None and sim(e, ht[pair]) >= NEAR and exp[i][2] and not _latin(e, ht[pair]):
                flags.append({"kind": "garbled", "expected": e, "heard": ht[pair]})
            elif (
                meaning(e) and not any(e in ht[j] for j in hz)
            ):  # glued ماشترى keeps its ما; even an unsure negation: a flipped meaning costs more than a false alarm
                flags.append({"kind": "dropped", "expected": e, "heard": None})
            else:
                continue
            hit.add(i)
            if pair is not None and flags[-1]["kind"] != "dropped":
                used.add(pair)
        rest = [i for i in ez if i not in hit and exp[i][2]]
        if len(rest) >= 2:  # two or more sure words replaced or gone at the join
            heard_txt = " ".join(ht[j] for j in hz if j not in used) or None
            kind = "garbled" if heard_txt else "missing"
            flags.append({"kind": kind, "expected": " ".join(et[i] for i in rest), "heard": heard_txt})
        for j in hz:
            h = ht[j]
            if (
                j not in used
                and len(_base(h)) > 3
                and h not in keep
                and any(sim(h, r) >= MATCH for r in removed)
            ):
                flags.append({"kind": "removed-heard", "expected": None, "heard": h})
    # a word heard twice in a row across the join that the source says once
    for a, b in itertools.pairwise(heard):
        if near(a[1]) and near(b[1]) and len(a[0]) > 2 and sim(a[0], b[0]) >= MATCH and not _twice(et, a[0]):
            flags.append({"kind": "repeat", "expected": None, "heard": a[0]})
    seen, out = set(), []
    for f in flags:
        k = (f["kind"], f["expected"], f["heard"])
        if k not in seen:
            seen.add(k)
            out.append(f)
    return out


def _latin(a: str, b: str) -> bool:
    """Both ASCII: brand spellings (cloud / claude) differ for reasons that have nothing to do with the cut."""
    return a.isascii() and b.isascii()


def _twice(toks: list[str], w: str) -> bool:
    """The expected words also repeat `w` back to back (a natural repeat)."""
    return any(sim(a, w) >= MATCH and sim(b, w) >= MATCH for a, b in itertools.pairwise(toks))


def kept_words(edl: Edl, words_by_clip: dict[str, list[dict]]) -> list[dict]:
    """Source words that survive the cut, with their program mid-time: [{pt, sure, tok, w, clip, st}]."""
    out = []
    for p in edl.pieces:
        if "hold" in p:
            continue
        for w in words_by_clip.get(p["clip"], []):
            mid = (w["t0"] + w["t1"]) / 2
            tok = _tok(w["w"])
            if tok and p["in"] <= mid < p["out"]:
                out.append(
                    {
                        "pt": p["start"] + mid - p["in"],
                        "sure": min(mid - p["in"], p["out"] - mid) >= BAND,
                        "tok": tok,
                        "w": w["w"],
                        "clip": p["clip"],
                        "st": mid,
                    }
                )
    out.sort(key=lambda x: x["pt"])
    return out


def check(
    edl: Edl, words_by_clip: dict[str, list[dict]], program: list[dict], only: set[int] | None = None
) -> list[dict]:
    """Every join of the edl (or only piece indexes `only`): {k, t, clip, out, in, hold, expected, heard, flags}.
    `program` = program-time words."""
    kept = kept_words(edl, words_by_clip)
    heard = [(k, (w["t0"] + w["t1"]) / 2, w["w"]) for w in program if (k := _tok(w["w"]))]
    res = []
    for k, p in enumerate(edl.pieces[1:], 1):
        if only is not None and k not in only:
            continue
        prev, j = edl.pieces[k - 1], p["start"]
        lo, hi = j - SIDE, j + SIDE
        ex = [(w["tok"], w["pt"], w["sure"], w) for w in kept if lo <= w["pt"] < hi]
        hd = [(t, m) for t, m, _ in heard if lo <= m < hi]
        removed = []
        if prev["clip"] == p["clip"] and "hold" not in prev and "hold" not in p and p["in"] > prev["out"]:
            removed = [
                t
                for w in words_by_clip.get(p["clip"], [])
                if prev["out"] + CUT_BAND <= (w["t0"] + w["t1"]) / 2 < p["in"] - CUT_BAND
                and (t := _tok(w["w"]))
            ]
        flags = compare([x[:3] for x in ex], hd, removed, j)
        res.append(
            {
                "k": k,
                "t": round(j, 2),
                "clip": prev["clip"],
                "out": prev.get("out") if "hold" not in prev else None,
                "in": p["in"] if "hold" not in p else None,
                "hold": "hold" in p or "hold" in prev,
                "expected": _split([(w["w"], pt) for _, pt, _s, w in ex], j),
                "heard": _heard_text(program, j),
                "flags": flags,
            }
        )
    return res


def confirm(project, edl: Edl, words_by_clip: dict[str, list[dict]], res: list[dict]) -> list[dict]:
    """Second opinion on the flagged joins: listen to just ~2.2 s either side of each (one Studio pass over the
    excerpts) and keep a flag only if it shows there too. The whole-program pass drifts over 13 minutes and
    mis-hears word timing, which causes most false alarms."""
    from vedit.cut import splice

    bad = [j for j in res if j["flags"]]
    if not bad:
        return res
    audio, sr = splice.read_wav(project.paths.program / "program.wav")
    starts = [max(0.0, j["t"] - SIDE) for j in bad]
    pieces = [splice.cut(audio, sr, s, s + 2 * SIDE) for s in starts]
    heard = splice.listen(project, pieces, sr, name="joins-confirm", gap=splice.PROGRAM_GAP)
    again = {}
    for j, s, ws in zip(bad, starts, heard, strict=True):
        local = [{"t0": s + w.start, "t1": s + w.end, "w": w.text} for w in ws]
        (r,) = check(edl, words_by_clip, local, only={j["k"]})
        again[j["k"]] = r
    return [again.get(j["k"], j) for j in res]


def _split(items: list[tuple[str, float]], j: float) -> list[str]:
    return [" ".join(w for w, t in items if t < j), " ".join(w for w, t in items if t >= j)]


def _heard_text(program: list[dict], j: float) -> list[str]:
    return _split(
        [
            (w["w"], (w["t0"] + w["t1"]) / 2)
            for w in program
            if j - SIDE <= (w["t0"] + w["t1"]) / 2 < j + SIDE
        ],
        j,
    )


def reason(f: dict) -> str:
    k, e, h = f["kind"], f["expected"], f["heard"]
    return {
        "clipped": f"clipped word: {e} heard as {h}",
        "garbled": f"garbled: {e} heard as {h}",
        "missing": f"words missing at the join: {e}",
        "dropped": f"dropped meaning word: {e}",
        "removed-heard": f"removed word still heard: {h}",
        "repeat": f"word heard twice across the join: {h}",
    }[k]


# ---- program transcription (Studio, cached) ----


def program_key(project, wav, edl_path) -> str:
    return hash_of(
        sample_hash(wav) or "",
        project.lang,
        project.dialect or "",
        project.hint or "",
        sample_hash(edl_path) or "",
    )


def cached(paths, key: str) -> list[dict] | None:
    meta, f = paths.program / "P.words.meta.json", paths.program / "P.words.json"
    try:
        if json.loads(meta.read_text())["key"] == key:
            return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError):
        pass
    return None


def program_words(project, edl: Edl, key: str, force: bool = False) -> list[dict]:
    """Studio transcript of program.wav as program-time words with their source (clip, time); cached by `key`."""
    paths = project.paths
    if not force and (ws := cached(paths, key)) is not None:
        return ws
    t = studio.transcribe(
        paths.program / "program.wav",
        project.lang,
        project.dialect,
        project.hint,
        fillers="keep",
        vad=False,
        cache_dir=paths.studio,
        log=log_path(paths.root, "joins"),
    )
    ws = []
    for w in t.words:
        clip, st = edl.src(w.start)
        ws.append(
            {"t0": round(w.start, 3), "t1": round(w.end, 3), "w": w.text, "clip": clip, "st": round(st, 3)}
        )
    paths.program.mkdir(parents=True, exist_ok=True)
    (paths.program / "P.words.json").write_text(json.dumps(ws, ensure_ascii=False), encoding="utf-8")
    (paths.program / "P.words.meta.json").write_text(
        json.dumps({"key": key, "words": len(ws)}), encoding="utf-8"
    )
    return ws
