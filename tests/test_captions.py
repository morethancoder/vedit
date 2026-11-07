from vedit.formats import captions as capmod
from vedit.formats import layout as lay
from vedit.project import Output


def W(text, t0, t1):
    return {"w": text, "t0": t0, "t1": t1}


ADV = {}  # every char 0.6 em


def test_pages_break_on_pause_and_sentence_end():
    words = [W("one", 0, 0.3), W("two.", 0.35, 0.6), W("three", 0.7, 1.0), W("four", 2.0, 2.3)]
    pgs = capmod.pages_of(words, 2000, ADV)
    assert [[w["w"] for w in p] for p in pgs] == [["one", "two."], ["three"], ["four"]]


def test_pages_fit_two_lines_of_the_width():
    words = [W("abcdefghij", i * 0.3, i * 0.3 + 0.25) for i in range(6)]  # each 10 chars = 384 px at 64 px
    pgs = capmod.pages_of(words, 800, ADV)  # two words per line, two lines per page
    assert [len(p) for p in pgs] == [4, 2]


def test_page_html_hides_pages_in_pauses_and_highlights_words():
    class Pk:
        data = {"colors": {"accent": "#FFD60A"}, "font": {"text": "X"}}  # noqa: RUF012

        def advances(self):
            return {}

    o = Output("r", "short", "9:16", ["tiktok"], None, "burned")
    g = lay.geometry(o, points=[{"t": 0, "x": 0}], t0=10, t1=20)
    words = [W("hi", 11, 11.4), W("there", 11.45, 11.8), W("later", 15, 15.4)]
    html = capmod.page_html(g, words, [(14.5, 16)], Pk(), None, "en")
    assert 'id="cp0"' in html and 'id="cp1"' not in html  # the second page falls in the pause
    assert '"#FFD60A" }, 1.000)' in html  # first word lit at its own time, local to the output
    assert 'data-width="1080" data-height="1920"' in html
