import json

import numpy as np
import pytest
import soundfile as sf

from vedit.cut import refine, signal, splice
from vedit.cut.cutsfile import WordCut
from vedit.project import Paths, Project

SR = 1000


def words(texts):
    return [{"t0": float(i), "t1": i + 0.9, "w": t} for i, t in enumerate(texts)]


def wc(i0, i1, label="x", clip="A"):
    return WordCut(clip, "phrase", label, "", i0, i1, float(i0), float(i1 + 1))


def test_lcs_and_score_prefers_dropping_removed():
    before, after, gone = ["a", "b"], ["c", "d"], ["x", "y"]
    good = refine.score(before, after, gone, ["a", "b", "c", "d"], 2, 4, 2, 4)
    bad = refine.score(before, after, gone, ["a", "b", "x", "y", "c", "d"], 2, 4, 2, 4)
    assert good > bad
    assert refine.lcs(["a", "b"], ["a", "q", "b"]) == 2


def test_candidates_quiet_points():
    db = np.zeros(1200)
    db[300:310] = -60
    db[500:510] = -50
    db[700:710] = -55
    c = refine.candidates(db, 5.0, 7.0)
    assert c and len(c) <= refine.K * refine.K
    assert all(e > s + 0.05 for s, e in c)
    assert any(abs(s - 5.0) < 0.1 for s, _ in c)


def test_pick_tie_goes_to_quietest_join():
    a = (1.0, -20.0, 1.0, 2.0, "a")
    b = (1.001, -50.0, 1.5, 2.5, "a")
    assert refine.pick([a, b])[1:3] == (1.5, 2.5)
    assert refine.pick([(2.0, -10, 0, 1, "a"), (1.0, -90, 5, 6, "b")])[1] == 0


def test_context_tokens():
    w = words(list("abcdefghij"))
    assert refine.context(wc(5, 6), w) == (list("bcde"), list("hij"), ["f", "g"])


@pytest.fixture
def proj(tmp_path):
    p = Project(tmp_path, "t", "ar", {})
    paths = Paths(tmp_path)
    paths.media.mkdir(parents=True)
    noise = np.random.default_rng(0).normal(0, 0.1, 40 * SR).astype("float32")
    sf.write(str(paths.media / "A-48k.wav"), noise, SR)
    return p, paths


def test_run_caches_and_relistens_only_edited(proj, monkeypatch):
    p, paths = proj
    calls = []

    def fake(project, pieces, sr, *, name="listen", gap=splice.GAP):
        calls.append(len(pieces))
        return [[splice.Heard(0, 0.1, "q")] for _ in pieces]

    monkeypatch.setattr(splice, "listen", fake)
    w = words([f"w{i}" for i in range(40)])
    cuts = [wc(10, 11, "p"), wc(25, 25, "q")]
    r = refine.run(p, paths, cuts, {"A": w})
    assert len(calls) == 1 and r.listened == 2 and r.cached == 0 and len(r) == 2
    assert set(json.loads((paths.edl / "refined.json").read_text())) == {c.key for c in cuts}
    r2 = refine.run(p, paths, cuts, {"A": w})
    assert len(calls) == 1 and r2.cached == 2 and r2.listened == 0
    w[26]["w"] = "changed"  # context of the second cut only
    r3 = refine.run(p, paths, cuts, {"A": w})
    assert len(calls) == 2 and r3.listened == 1 and r3.cached == 1 and len(r3) == 2


def test_run_winner_drops_removed_words(proj, monkeypatch):
    p, paths = proj
    w = words(["a", "b", "x", "y", "c", "d"] + ["z"] * 34)
    cut = wc(2, 3, "x y")
    db = signal.envelope_of(splice.read_wav(paths.media / "A-48k.wav")[0], SR)
    cands = refine.candidates(db, cut.w0, cut.w1)
    best = len(cands) - 1

    def fake(project, pieces, sr, *, name="listen", gap=0):
        ok, bad = ["a", "b", "c", "d"], ["a", "x", "y", "c"]
        return [[splice.Heard(0, 0.1, t) for t in (ok if i == best else bad)] for i in range(len(pieces))]

    monkeypatch.setattr(splice, "listen", fake)
    e = refine.run(p, paths, [cut], {"A": w})[cut.key]
    assert (e["in"], e["out"]) == cands[best] and e["heard"] == "a b c d"


def test_pinned_cuts_not_listened(proj, monkeypatch):
    p, paths = proj
    calls = []
    monkeypatch.setattr(splice, "listen", lambda *a, **k: calls.append(1))
    c = wc(3, 3)
    c.pin = (3.0, 3.5)
    assert len(refine.run(p, paths, [c], {"A": words(["w"] * 10)})) == 0
    assert not calls
