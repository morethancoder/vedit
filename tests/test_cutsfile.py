import pytest

from vedit.cut import cutsfile
from vedit.cut.cutsfile import CutsError, load, resolve


def mk(*items):
    return [{"t0": t, "t1": t + 0.3, "w": w} for t, w in items]


WORDS = {
    "A": mk(
        (10.0, "أنا"), (10.5, "يعني"), (11.0, "شنو"), (11.5, "هذا"), (12.0, "الشي"),
        (13.0, "خلي"), (13.5, "أرجع"), (14.0, "ااا"), (15.0, "إم"), (16.0, "um"),
        (30.0, "يعني"), (31.0, "شنو"),
    )
}  # fmt: skip
DUR = {"A": 40.0}


def cf_of(tmp_path, text):
    f = tmp_path / "cuts.yaml"
    f.write_text(text)
    return load(f)


def test_every_form_parses(tmp_path):
    cf = cf_of(
        tmp_path,
        """
pauses: { max: 0.6 }
fillers: true
cuts:
  - {near: A 10.5, say: "يعني", why: filler, window: 2}
  - {near: A 12, from: "هذا الشي", to: "خلي أرجع"}
keep: [{near: A 15, say: "إم"}]
pins: [{near: A 10.5, in: 10.4, out: 10.9}]
chapters: [{near: A 11, title: T, kicker: K, logo: octopus}]
end: last-word
""",
    )
    assert cf.pauses == {"max": 0.6, "keep": 0.3}
    assert cf.cuts[0].window == 2 and cf.cuts[1].from_ == "هذا الشي"
    assert cf.chapters[0].logo == "octopus" and cf.end == "last-word"


@pytest.mark.parametrize(
    "text,frag",
    [
        ("cut: []", "Did you mean 'cuts'"),
        ("cuts: [{near: A 1, say: x, wnidow: 2}]", "Did you mean 'window'"),
        ("cuts: [{say: x}]", "needs 'near'"),
        ("cuts: [{near: A 1}]", "needs 'say'"),
        ("cuts: [{near: A 1, say: x, from: y, to: z}]", "both"),
        ("cuts: [{near: oops, say: x}]", "bad near"),
        ("pins: [{near: A 1, in: 3, out: 2}]", "must come after"),
        ("end: first-word", "last-word"),
        ("fillers: 3", "true or false"),
        ("cuts: [{near: A 1, say: x, window: 0}]", "above 0"),
    ],
)
def test_errors(tmp_path, text, frag):
    with pytest.raises(CutsError, match=frag):
        cf_of(tmp_path, text)


def test_resolve_say_and_from_to(tmp_path):
    cf = cf_of(
        tmp_path,
        """
fillers: false
cuts:
  - {near: A 10.5, say: "يعني شنو"}
  - {near: A 12, from: "هذا الشي", to: "خلي أرجع"}
""",
    )
    cuts, problems = resolve(cf, WORDS, DUR)
    assert problems == []
    a, b = cuts
    assert (a.i0, a.i1, a.w0, a.w1) == (1, 2, 10.5, 11.5)
    assert (b.i0, b.i1, b.w0, b.w1) == (3, 6, 11.5, 14.0)
    assert b.label == "هذا الشي … خلي أرجع"


def test_last_word_ends_at_duration(tmp_path):
    cf = cf_of(tmp_path, "fillers: false\ncuts: [{near: A 31, say: شنو}]")
    (c,), _ = resolve(cf, WORDS, DUR)
    assert c.w1 == 40.0


def test_window_overrides(tmp_path):
    far = "cuts: [{near: A 20, say: 'هذا الشي'%s}]"
    cf = cf_of(tmp_path, "fillers: false\n" + far % "")
    _, problems = resolve(cf, WORDS, DUR)
    assert len(problems) == 1 and problems[0]["candidates"]
    cf = cf_of(tmp_path, "fillers: false\n" + far % ", window: 12")
    cuts, problems = resolve(cf, WORDS, DUR)
    assert problems == [] and cuts[0].i0 == 3


def test_problems_never_skipped(tmp_path):
    cf = cf_of(
        tmp_path,
        """
fillers: false
cuts:
  - {near: A 10.5, say: "كلام غير موجود"}
  - {near: A 10.5, say: "يعني"}
  - {near: A 12, from: "هذا", to: "غير موجود"}
  - {near: A 10.5, say: "أنا"}
""",
    )
    cuts, problems = resolve(cf, WORDS, DUR)
    assert [p["cut"] for p in problems] == [0, 2]
    assert problems[0]["text"] == "كلام غير موجود" and problems[0]["candidates"]
    assert "no match" in problems[0]["error"]
    assert len(cuts) == 2


def test_fillers_and_keep(tmp_path):
    cf = cf_of(tmp_path, "cuts: []")
    cuts, _ = resolve(cf, WORDS, DUR)
    assert [(c.kind, c.label) for c in cuts] == [("filler", "ااا"), ("filler", "إم"), ("filler", "um")]
    cf = cf_of(tmp_path, "keep: [{near: A 15, say: إم}]")
    cuts, problems = resolve(cf, WORDS, DUR)
    assert [c.label for c in cuts] == ["ااا", "um"] and problems == []
    cf = cf_of(tmp_path, "fillers: false")
    assert resolve(cf, WORDS, DUR)[0] == []
    assert cutsfile.FILLERS.match("اااا") and not cutsfile.FILLERS.match("يعني")


def test_keep_unresolved_is_a_problem(tmp_path):
    cf = cf_of(tmp_path, "keep: [{near: A 15, say: 'مفقود'}]")
    _, problems = resolve(cf, WORDS, DUR)
    assert problems[0]["section"] == "keep"


def test_pin_replaces_overlapping_cut(tmp_path):
    cf = cf_of(
        tmp_path,
        """
fillers: false
cuts: [{near: A 10.5, say: "يعني شنو"}]
pins: [{near: A 10.5, in: 10.4, out: 10.9}]
""",
    )
    (c,), _ = resolve(cf, WORDS, DUR)
    assert c.kind == "phrase" and c.pin == (10.4, 10.9)


def test_pin_only_cut(tmp_path):
    cf = cf_of(tmp_path, "fillers: false\npins: [{near: A 20, in: 20.5, out: 22}]")
    (c,), problems = resolve(cf, WORDS, DUR)
    assert (
        problems == [] and c.kind == "pin" and (c.i0, c.w0, c.w1, c.pin) == (None, 20.5, 22.0, (20.5, 22.0))
    )


def test_pin_picks_nearest_overlapping_cut(tmp_path):
    cf = cf_of(
        tmp_path,
        """
fillers: false
cuts:
  - {near: A 10.5, say: "يعني"}
  - {near: A 11, say: "شنو"}
pins: [{near: A 11, in: 10.6, out: 11.4}]
""",
    )
    cuts, _ = resolve(cf, WORDS, DUR)
    assert [c.pin for c in cuts] == [None, (10.6, 11.4)]


def test_end_never_runs_backwards(tmp_path):
    # fixture shape: the ASR's next word is stamped before the span ends (761.04-761.76, then 760.64)
    w = {"A": [{"t0": 761.04, "t1": 761.36, "w": "هسا"}, {"t0": 761.36, "t1": 761.76, "w": "حاليا"},
               {"t0": 760.64, "t1": 760.64, "w": "ه"}]}  # fmt: skip
    cf = cf_of(tmp_path, "fillers: false\ncuts: [{near: A 761, say: هسا حاليا}]")
    (c,), _ = resolve(cf, w, {"A": 800.0})
    assert c.w1 == 761.76 and c.w1 > c.w0
