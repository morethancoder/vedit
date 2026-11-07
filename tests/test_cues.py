import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from vedit.cut.cutsfile import Chapter, CutsFile
from vedit.graphics import cues as cu
from vedit.graphics.pack import BUILTIN
from vedit.report import VeditError
from vedit.words import Edl

ROOTS = [BUILTIN]
VOCAB = [
    "alpha",
    "bravo",
    "charlie",
    "delta",
    "echo",
    "foxtrot",
    "golf",
    "hotel",
    "india",
    "juliet",
    "kilo",
    "lima",
    "mike",
    "november",
    "oscar",
    "papa",
]
# word k is spoken at k * 0.5 s; "w<k>" names are unique per position, so any phrase is unambiguous
WORDS = {"A": [{"t0": k * 0.5, "t1": k * 0.5 + 0.4, "w": f"{VOCAB[k % 16]}{k}"} for k in range(80)]}
# source 0-10 kept at program 0, source 10-14 cut away, source 14-40 kept at program 10; total 36
EDL = Edl(
    {
        "pieces": [
            {"clip": "A", "in": 0, "out": 10, "start": 0},
            {"clip": "A", "in": 14, "out": 40, "start": 10},
        ],
        "total": 36.0,
    }
)


def w(k, n=1):
    return " ".join(x["w"] for x in WORDS["A"][k : k + n])


def run(tmp_path, text, project=None, edl=EDL, words=WORDS):
    (tmp_path / "cues.yaml").write_text(text)
    paths = SimpleNamespace(cues=tmp_path / "cues.yaml", root=tmp_path, custom=tmp_path / "custom")
    return cu.load(project or SimpleNamespace(style=None), paths, edl, words, roots=ROOTS)


LABEL = "logo: telegram\n    kicker: k\n    title: t\n"


def label(at, extra=""):
    return f'  - type: label\n    at: "{at}"\n    near: A {extra}\n    ' + LABEL


def test_anchor_start_and_default_end(tmp_path):
    [c] = run(tmp_path, "cues:\n" + label(w(4, 2), "2.0"))
    assert (c.id, c.clip, c.src, c.start) == ("label-1", "A", 2.0, 2.0)
    assert c.end == 2.0 + cu.DEFAULT_LEN["label"]
    assert (
        c.style == "base" and c.fields == {"logo": "telegram", "kicker": "k", "title": "t"} and not c.problems
    )
    assert len(c.key) == 16


def test_start_goes_through_the_edl(tmp_path):
    [c] = run(tmp_path, "cues:\n" + label(w(30), "15.0"))  # source 15.0 -> program 11
    assert (c.src, c.start) == (15.0, 11.0)


def test_until_for_end_and_defaults(tmp_path):
    base = label(w(2, 2), "1.0")
    [a] = run(tmp_path, f'cues:\n{base}    until: "{w(8, 2)}"\n')
    assert a.end == pytest.approx(4.9)  # t1 of the last until word
    [b] = run(tmp_path, f"cues:\n{base}    for: 3\n")
    assert b.end == 4.0
    [d] = run(tmp_path, f"cues:\n{base}    until: end\n")
    assert d.end == 36.0
    with pytest.raises(VeditError, match="not both"):
        run(tmp_path, f"cues:\n{base}    for: 3\n    until: end\n")
    with pytest.raises(VeditError, match="not spoken within"):
        run(tmp_path, f'cues:\n{base}    until: "nothing here"\n')


def test_default_lengths_per_type(tmp_path):
    txt = f'''cues:
  - {{type: chip, at: "{w(2)}", near: A 1.0, label: l, code: c}}
  - {{type: big-number, at: "{w(2)}", near: A 1.0, word: "1M"}}
  - {{type: plug, at: "{w(2)}", near: A 1.0}}
'''
    ends = [c.end - c.start for c in run(tmp_path, txt)]
    assert ends == [8.0, 5.0, 18.0]


def test_custom_requires_for(tmp_path):
    (tmp_path / "custom").mkdir()
    (tmp_path / "custom" / "x.html").write_text("<div></div>")
    head = f'cues:\n  - type: custom\n    at: "{w(2)}"\n    near: A 1.0\n    file: custom/x.html\n'
    with pytest.raises(VeditError, match="needs `for"):
        run(tmp_path, head)
    [c] = run(tmp_path, head + "    for: 4\n")
    assert c.end - c.start == 4
    with pytest.raises(VeditError, match="not found under the project"):
        run(tmp_path, head.replace("x.html", "nope.html") + "    for: 4\n")


def test_kinetic_default_end_and_spoken(tmp_path):
    txt = f'cues:\n  - type: kinetic\n    at: "{w(10, 3)}"\n    near: A 5.0\n    words: "one two three"\n'
    [c] = run(tmp_path, txt)
    assert c.spoken[:3] == [5.0, 5.5, 6.0]
    assert c.end == pytest.approx(6.0 + cu.KINETIC_TAIL)
    # more shown words than the anchor has: keeps reading the transcript onward
    [c2] = run(tmp_path, txt.replace("one two three", "a b c d e"))
    assert c2.end == pytest.approx(7.0 + cu.KINETIC_TAIL)


def test_doodle_beats_and_default_end(tmp_path):
    txt = f"""cues:
  - type: doodle
    at: "{w(4, 2)}"
    near: A 2.0
    scene: flood
    beats: {{bot: "{w(5)}", crash: "{w(9, 2)}", second: "{w(60)}", flood: "no such words"}}
    for: 10
"""
    [c] = run(tmp_path, txt)
    assert c.beats == {"bot": 2.5, "crash": 4.5}
    assert c.end == 12.0  # `for` wins; `second` is past the source span + 5 s
    assert len(c.problems) == 2 and "second" in c.problems[0] and "Closest" in c.problems[1]


def test_doodle_default_end_is_last_beat_plus_tail(tmp_path):
    txt = f'cues:\n  - type: doodle\n    at: "{w(4, 2)}"\n    near: A 2.0\n    scene: flood\n    beats: {{bot: "{w(9)}"}}\n'
    assert run(tmp_path, txt)[0].end == 4.5 + cu.DOODLE_TAIL


def test_beat_spoken_before_the_anchor_by_under_a_second(tmp_path):
    txt = f'cues:\n  - type: doodle\n    at: "{w(6)}"\n    near: A 3.0\n    scene: flood\n    beats: {{bot: "{w(5)}"}}\n'
    assert run(tmp_path, txt)[0].beats == {"bot": 2.5}


def test_words_slots(tmp_path):
    txt = f'cues:\n  - type: plug\n    at: "{w(2)}"\n    near: A 1.0\n    url: "{w(6, 2)}"\n    trial: "{w(20)}"\n'
    [c] = run(tmp_path, txt)
    assert c.times == {"url": 3.0, "trial": 5.0 + 5.0 + 0.0}  # source 10.0 is cut away: lands on program 10


def test_cut_away_anchor_is_reported_not_dropped(tmp_path):
    [c] = run(tmp_path, "cues:\n" + label(w(22, 2), "11.0"))  # source 11.0-12.0 is inside the cut
    assert len(c.problems) == 1 and "cut away" in c.problems[0]
    assert c.start == 10.0


def test_anchor_without_near_needs_exactly_one_match(tmp_path):
    [c] = run(tmp_path, f'cues:\n  - type: label\n    at: "{w(4, 2)}"\n    {LABEL}')
    assert c.src == 2.0
    two = {"A": WORDS["A"], "B": WORDS["A"]}
    with pytest.raises(VeditError, match="matches 2 places"):
        run(tmp_path, f'cues:\n  - type: label\n    at: "{w(4, 2)}"\n    {LABEL}', words=two)
    with pytest.raises(VeditError, match="no match"):
        run(tmp_path, f'cues:\n  - type: label\n    at: "zzz"\n    {LABEL}')


def test_ambiguous_with_near_is_reported(tmp_path):
    rep = {"A": [{"t0": k, "t1": k + 0.4, "w": "xyz"[k % 3]} for k in range(12)]}
    with pytest.raises(VeditError, match="matches"):
        run(
            tmp_path, 'cues:\n  - type: label\n    at: "x"\n    near: A 4.5\n    ' + LABEL, words=rep, edl=EDL
        )


def test_validation_collects_everything(tmp_path):
    txt = f'''cues:
  - {{type: label, at: "{w(2)}", near: A 1.0, logo: nope, kicker: k, title: t, subb: s}}
  - {{type: label, at: "{w(2)}", near: A 1.0, logo: telegram, kicker: k}}
  - {{type: bogus, at: "{w(2)}", near: A 1.0}}
  - {{type: chapter, at: "{w(2)}", near: A 1.0, title: t}}
  - {{type: big-number, at: "{w(2)}", near: A 1.0, word: 3, pre: [x]}}
'''
    with pytest.raises(VeditError) as e:
        run(tmp_path, txt)
    m = str(e.value)
    assert "5 problem" not in m  # counted below
    for want in (
        "unknown field 'subb'",
        "did you mean 'sub'",
        "logo 'nope' is not in the style",
        "needs 'title'",
        "no template for cue type 'bogus'",
        "come from cuts.yaml",
        "'pre' should be text",
    ):
        assert want in m, want
    assert e.value.next


def test_custom_logo_from_project(tmp_path):
    (tmp_path / "custom" / "logos").mkdir(parents=True)
    (tmp_path / "custom" / "logos" / "ptb.svg").write_text("<svg/>")
    [c] = run(tmp_path, "cues:\n" + label(w(4), "2.0").replace("telegram", "ptb"))
    assert c.fields["logo"] == "ptb"


def test_ids_explicit_and_counted(tmp_path):
    txt = f'''cues:
  - {{type: chip, at: "{w(2)}", near: A 1.0, label: l, code: c}}
  - {{type: chip, id: mine, at: "{w(8)}", near: A 4.0, label: l, code: c}}
  - {{type: chip, at: "{w(12)}", near: A 6.0, label: l, code: c}}
'''
    assert [c.id for c in run(tmp_path, txt)] == ["chip-1", "mine", "chip-3"]
    with pytest.raises(VeditError, match="duplicate id"):
        run(tmp_path, txt.replace("id: mine", "id: chip-1"))


def test_unknown_top_level_key_and_empty_file(tmp_path):
    with pytest.raises(VeditError, match="unknown top-level key"):
        run(tmp_path, "cuez: []\n")
    assert run(tmp_path, "cues: []\n") == []
    assert run(tmp_path, "") == []


def test_style_precedence(tmp_path):
    (tmp_path / "st" / "other").mkdir(parents=True)
    for n in ("other", "third", "fourth"):
        d = tmp_path / "st" / n
        d.mkdir(exist_ok=True)
        (d / "pack.yaml").write_text(f"name: {n}\nextends: base\n")
    global ROOTS
    old, ROOTS = ROOTS, [tmp_path / "st", BUILTIN]
    try:
        body = f'  - {{type: chip, at: "{w(2)}", near: A 1.0, label: l, code: c}}\n'
        assert run(tmp_path, "cues:\n" + body)[0].style == "base"
        assert run(tmp_path, "cues:\n" + body, project=SimpleNamespace(style="third"))[0].style == "third"
        assert (
            run(tmp_path, "style: other\ncues:\n" + body, project=SimpleNamespace(style="third"))[0].style
            == "other"
        )
        cue_style = body.replace("code: c}", "code: c, style: fourth}")
        assert run(tmp_path, "style: other\ncues:\n" + cue_style)[0].style == "fourth"
        with pytest.raises(VeditError, match="not found"):
            run(tmp_path, "style: nope\ncues:\n" + body)
    finally:
        ROOTS = old


def test_key_changes_with_content_only(tmp_path):
    a = run(tmp_path, "cues:\n" + label(w(4), "2.0"))[0].key
    assert run(tmp_path, "cues:\n" + label(w(4), "2.0"))[0].key == a
    assert run(tmp_path, "cues:\n" + label(w(4), "2.0").replace("title: t", "title: u"))[0].key != a


def test_chapters_pair_with_holds(tmp_path):
    edl = Edl(
        {
            "pieces": [
                {"clip": "A", "in": 0, "out": 10, "start": 0},
                {"clip": "A", "in": 10, "hold": 2.0, "start": 10, "out": 10},
                {"clip": "A", "in": 10, "out": 20, "start": 12},
                {"clip": "A", "in": 20, "hold": 1.0, "start": 22, "out": 20, "sound": "continue"},
            ],
            "total": 30.0,
        }
    )
    cf = CutsFile(chapters=[Chapter("A 10", "Part one", "1", "telegram")])
    [c] = cu.chapters(cf, edl, packs_for_tests())
    assert (c.id, c.type, c.start, c.end) == ("chapter-1", "chapter", 9.5, 9.5 + 2.0 + 0.9)
    assert c.fields == {"title": "Part one", "kicker": "1", "logo": "telegram"} and c.clip == "A" and c.key
    with pytest.raises(VeditError, match="0 chapter"):
        cu.chapters(CutsFile(), edl, packs_for_tests())
    with pytest.raises(VeditError, match="logo 'zz'"):
        cu.chapters(CutsFile(chapters=[Chapter("A 10", "T", None, "zz")]), edl, packs_for_tests())
    with pytest.raises(VeditError, match="needs 'title'"):
        cu.chapters(CutsFile(chapters=[Chapter("A 10", "", None, None)]), edl, packs_for_tests())


def packs_for_tests():
    from vedit.graphics import pack

    return pack.load("base", ROOTS)


def test_chapter_logo_may_come_from_project(tmp_path):
    edl = Edl({"pieces": [{"clip": "A", "in": 0, "hold": 2.0, "start": 0, "out": 0}], "total": 2.0})
    cf = CutsFile(chapters=[Chapter("A 0", "T", None, "ptb")])
    [c] = cu.chapters(cf, edl, packs_for_tests(), logos={"ptb": Path("x.svg")})
    assert c.start == 0.0  # clamped: a hold at 0 cannot start 0.5 s earlier


def test_unquoted_yaml_boolean_beat_key_is_an_error(tmp_path):
    txt = f'cues:\n  - type: doodle\n    at: "{w(4)}"\n    near: A 2.0\n    scene: gate\n    beats: {{no: "{w(5)}"}}\n'
    with pytest.raises(VeditError, match="quote it"):
        run(tmp_path, txt)
    [c] = run(tmp_path, txt.replace("{no:", '{"no":'))
    assert c.beats == {"no": 2.5}


@pytest.mark.parametrize(
    "bad",
    [
        "Mine",
        "a_b",
        "x y",
        'q"x',
        "-x",
        "main",
        "root",
        "cam",
        "fade",
        "program",
        "sfx-1",
        "mt-big",
        "chapter-2",
    ],
)
def test_bad_and_reserved_ids_are_load_errors(tmp_path, bad):
    txt = f'cues:\n  - {{type: chip, id: {json.dumps(bad)}, at: "{w(2)}", near: A 1.0, label: l, code: c}}\n'
    with pytest.raises(VeditError, match="id") as e:
        run(tmp_path, txt)
    assert bad in str(e.value) and "problem" in str(e.value)


@pytest.mark.parametrize("good", ["a", "k-pressure", "9lives", "big-2"])
def test_good_ids_pass(tmp_path, good):
    txt = f'cues:\n  - {{type: chip, id: {good}, at: "{w(2)}", near: A 1.0, label: l, code: c}}\n'
    assert run(tmp_path, txt)[0].id == good


def _big(color):
    return f'cues:\n  - {{type: big-number, at: "{w(2)}", near: A 1.0, word: "5", color: "{color}"}}\n'


@pytest.mark.parametrize(
    "good", ["#fff", "#FAF9F5", "#faf9f580", "rgb(1, 2,3)", "rgba(1,2,3,.5)", "hsl(120, 50%, 40%)", "gold"]
)
def test_colour_accepts_css_colours(tmp_path, good):
    assert run(tmp_path, _big(good))[0].fields["color"] == good


@pytest.mark.parametrize(
    "bad", ["red;}</style><script>x</script>", "#12", "url(x)", "rgb(1,2,3);", "a b", "{{x}}"]
)
def test_colour_rejects_anything_else(tmp_path, bad):
    with pytest.raises(VeditError, match="not a CSS colour"):
        run(tmp_path, _big(bad))
