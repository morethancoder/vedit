import json
from pathlib import Path

import pytest

from vedit.project import Paths
from vedit.report import VeditError
from vedit.words import AmbiguousMatch, NoMatch, find, load, parse_near


def mk(*items):
    return [{"t0": t, "t1": t + 0.3, "w": w} for t, w in items]


WORDS = {
    "A": mk(
        (10.0, "أنا"), (10.5, "يعني"), (11.0, "شنو"), (11.5, "هذا"),
        (20.0, "يعني"), (20.5, "شنو"), (21.0, "راح"),
        (100.0, "يَعْنِي"), (100.5, "شنو"),
        (103.0, "يعني"), (103.5, "شنو"),
    )
}  # fmt: skip


def test_parse_near():
    assert parse_near("A 245.0") == ("A", 245.0)
    assert parse_near("B 92") == ("B", 92.0)
    for bad in ("245", "A", "A x", ""):
        with pytest.raises(VeditError):
            parse_near(bad)


def test_exact_nearest_of_two():
    s = find(WORDS, "يعني شنو", near="A 12")
    assert (s.clip, s.i0, s.i1, s.t0, s.t1) == ("A", 1, 2, 10.5, 11.3)
    assert find(WORDS, "يعني شنو", near="A 19").i0 == 4


def test_normalised_match():
    assert find(WORDS, "يعنى شنو", near="A 100.2").i0 == 7


def test_ambiguous_lists_candidates():
    with pytest.raises(AmbiguousMatch) as e:
        find(WORDS, "يعني شنو", near="A 101.5")
    assert "100.00" in str(e.value) and "103.00" in str(e.value)
    assert e.value.next


def test_missing_lists_closest():
    with pytest.raises(NoMatch) as e:
        find(WORDS, "يعني شنوو", near="A 20")
    assert "similarity" in str(e.value) and "20.00" in str(e.value)
    assert e.value.next
    with pytest.raises(NoMatch):
        find(WORDS, "يعني شنو", near="A 50")  # exists, but outside the window
    assert find(WORDS, "يعني شنو", near="A 50", window=40).t0 == 20.0


def test_unknown_clip_and_empty_phrase():
    with pytest.raises(VeditError):
        find(WORDS, "يعني", near="B 1")
    with pytest.raises(VeditError):
        find(WORDS, "...", near="A 1")


def test_load(tmp_path):
    paths = Paths(tmp_path)
    paths.words.mkdir(parents=True)
    (paths.words / "A.json").write_text(json.dumps(WORDS["A"]))
    assert load(paths, "A") == WORDS["A"]
    with pytest.raises(VeditError):
        load(paths, "Z")


REAL = Path.home() / "Demos/tele-a7-growth-story/work/A.words.json"


@pytest.mark.skipif(not REAL.exists(), reason="T fixture missing")
def test_real_words():
    words = json.loads(REAL.read_text())
    i = next(k for k in range(300, len(words) - 3) if words[k]["t0"] > 100)
    phrase = " ".join(w["w"] for w in words[i : i + 3])
    s = find({"A": words}, phrase, near=f"A {words[i]['t0'] + 1.5}", window=6)
    assert s.i0 == i and s.t0 == words[i]["t0"]


def _stut():
    ws = [
        {"t0": 10.0, "t1": 10.3, "w": "قبل"},
        {"t0": 10.4, "t1": 10.7, "w": "يعني"},
        {"t0": 10.9, "t1": 11.2, "w": "يعني"},
        {"t0": 11.3, "t1": 11.6, "w": "بعد"},
    ]
    return {"A": ws}


def test_stutter_picks_first_copy():
    from vedit.words import find

    assert find(_stut(), "يعني", "A 10.8").i0 == 1


def test_identical_but_not_adjacent_stays_ambiguous():
    import pytest

    from vedit.words import AmbiguousMatch, find

    w = _stut()
    w["A"].insert(2, {"t0": 10.75, "t1": 10.85, "w": "هو"})
    with pytest.raises(AmbiguousMatch):
        find(w, "يعني", "A 10.8")


def test_pick_overrides():
    import pytest

    from vedit.report import VeditError
    from vedit.words import find

    assert find(_stut(), "يعني", "A 10.8", pick="last").i0 == 2
    assert find(_stut(), "يعني", "A 10.8", pick=2).i0 == 2
    with pytest.raises(VeditError):
        find(_stut(), "يعني", "A 10.8", pick=3)
