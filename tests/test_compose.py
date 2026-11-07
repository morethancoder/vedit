"""Compose: type templates on synthetic placements, index.html structure, incremental regeneration, base pack."""

import itertools
import json
import re
from types import SimpleNamespace

import pytest

from vedit.graphics import compose, pages
from vedit.graphics import pack as packs
from vedit.graphics.cues import Cue
from vedit.graphics.plan import Placement, Plan
from vedit.project import Paths

BIG = {"side": "left", "fs": 240, "left": 300, "top": 260, "width": 500, "tuck": 0.45, "drift": 30}


@pytest.fixture
def base():
    return packs.load("base")


@pytest.fixture
def yellow():
    return packs.load("yellow-doodle", [packs.BUILTIN])


@pytest.fixture
def paths(tmp_path):
    p = Paths(tmp_path)
    (tmp_path / ".vedit" / "program").mkdir(parents=True)
    (tmp_path / ".vedit" / "program" / "proxy.mp4").write_bytes(b"x")
    return p


def env(paths, **kw):
    return pages.Env(paths, kw.get("lang", "ar"), None, kw.get("plug"), "demo", kw.get("logos", {}))


def cue(cid, typ, fields, start=10.0, end=16.0, **kw):
    c = Cue(
        cid, typ, "base", fields, "A", start, start, end, key=f"k-{cid}-{json.dumps(fields, sort_keys=True)}"
    )
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def pl(c, track=1, **kw):
    return Placement(c, c.start, c.end - c.start, track, **kw)


LABEL = {"logo": "octopus", "kicker": "قبل ٤ سنين", "title": "فتحت قناتي", "sub": "سطر"}


def items():
    return [
        pl(cue("intro", "label", LABEL), side="left", theme="dark"),
        pl(cue("big-1", "big-number", {"word": "1.7M", "pre": "من"}, 20, 25), track=2, big=BIG),
        pl(cue("ch-1", "chapter", {"title": "كيف بدأت", "kicker": "الجزء ١", "logo": "spark"}, 30, 33), 6),
        pl(
            cue(
                "dd",
                "doodle",
                {"scene": "flood", "beats": {"bot": "x", "crash": "y"}},
                40,
                50,
                beats={"bot": 41.0, "crash": 41.1},
            ),
            6,
        ),
    ]


def plan_of(its, total=60.0):
    zooms = [(0.0, 1.0, 960, 540), (12.0, 1.07, 1000, 400), (18.0, 1.0, 960, 540)]
    focus = [(p.start, p.end) for p in its if p.cue.type in ("chapter", "doodle", "screen")]
    return Plan(its, zooms, focus, [], total)


def write(paths, base, its, total=60.0):
    mattes = {f"mt-{p.id}": paths.mattes / f"mt-{p.id}.webm" for p in its if p.cue.type == "big-number"}
    edl = SimpleNamespace(fade_start=total - 1.6)
    return compose.write(paths, plan_of(its, total), lambda c: base, base, edl, env(paths), mattes)


def render(p, base, e):
    html = pages.render(p, base, e).html
    assert "{{" not in html and "}}" not in html
    assert f'data-composition-id="{p.id}"' in html and f'window.__timelines["{p.id}"]' in html
    assert "<template>" in html and f"const D = {round(p.dur, 3):g};" in html
    return html


# ---- templates ----


def test_label_sides_theme_and_blur(base, paths):
    e = env(paths)
    left = render(pl(cue("a", "label", LABEL), side="left", theme="dark"), base, e)
    assert "left: 150px" in left and "فتحت قناتي" in left and '<div class="sub">سطر</div>' in left
    assert '<svg class="logo"' in left and "var(--" not in left  # pack mark inlined, fills resolved
    assert base.data["themes"]["dark"]["shadow"] in left and "blurbg" not in left
    right = render(pl(cue("b", "label", LABEL), side="right", theme="light", blur=True), base, e)
    assert "right: 150px" in right and base.data["themes"]["light"]["text"] in right
    busy = render(pl(cue("c", "label", LABEL), side="left", theme="dark", blur=True), base, e)
    assert 'class="blurbg"' in busy and base.data["busy_shadow"] in busy and "backdrop-filter" in busy


def test_label_project_logo_is_an_image(base, paths, tmp_path):
    f = tmp_path / "custom" / "logos" / "ptb.svg"
    f.parent.mkdir(parents=True)
    f.write_text("<svg/>")
    html = render(
        pl(cue("a", "label", {**LABEL, "logo": "ptb"}), side="left"), base, env(paths, logos={"ptb": f})
    )
    assert '<img class="logo" src="assets/logos/ptb.svg"' in html


def test_kinetic_words_land_on_spoken_times_with_highlight(base, paths):
    c = cue("k", "kinetic", {"words": "«شنو البوت مو شغال؟!»", "highlight": ["مو شغال؟!»"]}, 100, 103,
            spoken=[100.2, 100.5, 100.9])  # fmt: skip
    html = render(pl(c, side="right", width=560), base, env(paths))
    assert "const at = [0.2, 0.5, 0.9, 1.15, ];" in html  # last shown word has no transcript word: +0.25
    assert html.count('class="w hl"') == 2 and html.count('class="w"') == 2
    assert "width: 560px" in html and "right: 150px" in html and 'dir="rtl"' in html


def test_chip_arabic_types_word_by_word(base, paths):
    c = cue("c", "chip", {"label": "قل", "code": "اربط لي الـ MCP"})
    html = render(pl(c, side="left"), base, env(paths))
    assert html.count('class="ch"') == 4 and "const n = 4;" in html and 'dir="rtl"' in html
    assert '<svg class="logo"' in html  # default mark when the cue names none (T: spark)
    latin = render(pl(cue("d", "chip", {"label": "say", "code": "npm i"}), side="left"), base, env(paths))
    assert latin.count('class="ch"') == 5 and "code mono" in latin


def test_big_number_uses_layout(base, paths):
    html = render(items()[1], base, env(paths))
    assert "left: 300px; top: 201px" in html  # top - pre_fs (53) - 6
    assert "font: 700 240px/1" in html and "letter-spacing: -0.03em" in html and ">1.7M<" in html


def test_chapter_and_doodle_placeholder(base, paths):
    ch = render(items()[2], base, env(paths))
    assert "كيف بدأت" in ch and "الجزء ١" in ch and "justify-content: center" in ch
    dd = pages.render(items()[3], base, env(paths))
    assert '<svg class="dz"' in dd.html and ">البوت<" in dd.html and ">طاح!<" in dd.html  # flood, drawn
    assert "const DRAW = [[" in dd.html and "{{" not in dd.html
    assert dd.sounds == [("focus", 0.0), ("beat", 1.0), ("beat", 1.1)]


def test_plug_without_preset_is_brand_text_only(base, paths):
    c = cue("p", "plug", {}, 10, 28, times={"url": 18.0})
    pg = pages.render(pl(c, 6), base, env(paths, plug="PowerTeleBot"))
    assert ">PowerTeleBot<" in pg.html and "phone" not in pg.html.split("<script>")[0].split("</style>")[-1]
    assert pg.sounds == [] and pg.media == {}


def test_plug_preset(base, paths, tmp_path, monkeypatch):
    d = tmp_path / "custom" / "plug"
    d.mkdir(parents=True)
    (d / "demo.mp4").write_bytes(b"x")
    (d / "plug.yaml").write_text("name: P\nurl: p.com\ntrial: try\ndemo: demo.mp4\n")
    monkeypatch.setattr(pages, "ffprobe_duration", lambda f: 16.0667)
    c = cue("p", "plug", {}, 10, 28, times={"url": 18.0, "trial": 20.5})
    pg = pages.render(pl(c, 6), base, env(paths))
    assert 'data-duration="16.067"' in pg.html and ">p.com<" in pg.html and ">try<" in pg.html
    assert pg.sounds == [("phone", 0.1), ("url", 9.35)] and pg.media == {
        "media/plug-demo.mp4": d / "demo.mp4"
    }


def test_screen_plays_the_source_proxy(base, paths, monkeypatch):
    src = paths.media / "proxy" / "B.mp4"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"x")
    monkeypatch.setattr(
        pages, "ffprobe_json", lambda f: {"streams": [{"codec_type": "video", "width": 1920, "height": 1080}]}
    )
    c = cue("s", "screen", {"source": "B", "from": 12.5, "title": "T", "steps": ["one", "two"]}, 10, 18)
    pg = pages.render(pl(c, 6), base, env(paths))
    assert 'src="media/src-B.mp4"' in pg.html and 'data-media-start="12.5"' in pg.html
    assert "width: 1100px; height: 619px" in pg.html and pg.html.count('class="step"') == 2
    assert pg.media == {"media/src-B.mp4": src}


def test_custom_copies_the_project_file(base, paths, tmp_path):
    f = tmp_path / "custom" / "intro.html"
    f.parent.mkdir(parents=True)
    f.write_text(
        '<template><div data-composition-id="mine"></div><script>window.__timelines["mine"]=tl;</script></template>'
    )
    html = pages.render(pl(cue("intro", "custom", {"file": "custom/intro.html"}), 6), base, env(paths)).html
    assert 'data-composition-id="intro"' in html and '__timelines["intro"]' in html and "mine" not in html


def test_custom_gets_the_packs_tokens_as_css_variables(yellow, base, paths, tmp_path):
    f = tmp_path / "custom" / "x.html"
    f.parent.mkdir(parents=True)
    f.write_text(
        '<template><div data-composition-id="m"></div><script>window.__timelines["m"]=tl;</script></template>'
    )
    p = pl(cue("cx", "custom", {"file": "custom/x.html"}), 6)
    html = pages.render(p, yellow, env(paths)).html
    assert html.index("<template>") < html.index("--vedit-") < html.index('data-composition-id="cx"></div>')
    for k in yellow.data["colors"]:
        assert f"--vedit-{k.replace('_', '-')}:" in html
    for k in yellow.data["font"]:
        assert f"--vedit-font-{k}:" in html
    for k in ("text", "sub", "kicker", "shadow"):
        assert f"--vedit-{k}:" in html
    assert "@font-face" in html
    other = pages.render(p, base, env(paths)).html
    assert other != html and pages.key(p, yellow, env(paths)) != pages.key(p, base, env(paths))
    assert "--vedit-accent: #" in pages.render(p, base, pages.Env(paths, "ar", "#123456", None, "d", {})).html


# ---- index ----


def test_index_structure(yellow, paths):
    res = write(paths, yellow, items())
    hf = paths.hf
    html = (hf / "index.html").read_text()
    audio = re.findall(r"<audio [^>]*>", html)
    assert audio and all("data-duration=" in a and 'id="sfx-' in a for a in audio)
    assert all((hf / s).is_file() for s in re.findall(r'src="(assets/[^"]+)"', html))
    assert not re.search(r'<script[^>]+src="https?:', html)  # GSAP is bundled, never a CDN
    assert (hf / "assets" / "gsap.min.js").read_bytes() == compose.GSAP_JS.read_bytes()
    assert 'src="assets/gsap.min.js"' in html and "GSAP 3.14.2" in compose.GSAP_JS.read_text()[:200]
    for src in re.findall(r'data-composition-src="([^"]+)"', html):
        assert (hf / src).is_file()
    cam = html.split('<div id="cam">')[1].split("<!-- layer: front -->")[0]
    assert 'id="big-1"' in cam and 'src="media/mt-big-1.webm"' in cam and 'id="intro"' not in cam
    assert 'tl.set("#cam", { scale: 1.07, transformOrigin: "1000px 400px" }, 12.000);' in html
    assert 'filter: "blur(20px) brightness(0.42)"' in html
    assert 'tl.fromTo("#fade", { opacity: 0 }, { opacity: 1, duration: 1.6' in html
    assert (hf / "media" / "program.mp4").is_symlink() and (hf / "assets" / "fonts").is_dir()
    assert {r[2] for r in res.sfx} == {
        "click-soft",
        "whoosh-short",
    }  # label, big, focus, beats; chapter silent
    beats = [r for r in res.sfx if r[0] in (41.0, 41.1)]
    assert len(beats) == 1  # back-to-back beats get one click
    assert json.loads((hf / "chunks.json").read_text())["bounds"][-1] == 60.0


def test_chunk_bounds_avoid_busy_time():
    b = compose.chunk_bounds([(140.0, 165.0)], 400.0)
    assert b[0] == 0.0 and b[-1] == 400.0
    assert not (140 - 0.25 <= b[1] <= 165.25) and 100 < b[1] < 220


# ---- incremental ----


def test_only_changed_cues_regenerate(base, paths):
    its = items()
    first = write(paths, base, its)
    assert sorted(first.written) == sorted(p.id for p in its) and first.index_changed
    mtimes = {f.name: f.stat().st_mtime_ns for f in (paths.hf / "compositions").glob("*.html")}
    again = write(paths, base, items())
    assert again.written == [] and not again.index_changed and len(again.reused) == len(its)
    assert mtimes == {f.name: f.stat().st_mtime_ns for f in (paths.hf / "compositions").glob("*.html")}
    changed = items()
    changed[0] = pl(cue("intro", "label", {**LABEL, "title": "عنوان ثاني"}), side="left", theme="dark")
    third = write(paths, base, changed)
    assert third.written == ["intro"]
    fewer = write(paths, base, changed[:-1])
    assert fewer.removed == ["dd"] and not (paths.hf / "compositions" / "dd.html").exists()


# ---- the base pack ----


def test_base_pack_is_complete(base, paths):
    types = {"label", "chip", "kinetic", "big-number", "chapter", "doodle", "screen", "plug", "custom"}
    assert types <= set(base.types())
    for t in types:
        base.template(t)  # slot headers parse
    for f in base.data["fonts"]:
        assert base.file(f["file"]) is not None
    for name, gain in base.data["sfx"].values():
        assert base.file(f"sfx/{name}.mp3") is not None and name in base.data["sfx_files"] and 0 < gain < 1
    assert {"base", "blur_css", "blur_motion", "logo_motion"} <= set(base.partials())
    for k in ("text", "sub", "kicker", "shadow"):
        assert all(k in base.data["themes"][t] for t in ("dark", "light"))
    assert base.data["logo_motion"]["spin"] == [] and "Ruqaa" not in base.data["font"]["hand"]


def test_base_is_neutral():
    """No yellow (T's accent and its tints) and no hand lettering anywhere in base's own files."""
    yellowish = re.compile(r"FFD60A|B08700|8A6A00|rgba\(255,\s*214,\s*10|Ruqaa", re.IGNORECASE)
    d = packs.BUILTIN / "base"
    for f in [d / "pack.yaml", *d.glob("types/*.html"), *d.glob("partials/*.html"), *d.glob("logos/*.svg")]:
        assert not yellowish.search(f.read_text(encoding="utf-8")), f
    assert not list(d.glob("fonts/*Ruqaa*"))


V1 = ("label", "chip", "kinetic", "big-number", "chapter", "doodle", "screen", "plug")


def test_yellow_doodle_owns_the_telegram_look(yellow):
    src = yellow.type_sources()
    assert all(src[t] == "yellow-doodle" for t in V1) and src["custom"] == "base"
    assert yellow.data["colors"]["accent"] == "#FFD60A" and "Aref Ruqaa" in yellow.data["font"]["hand"]
    assert yellow.file("fonts/ArefRuqaa-Bold.ttf").parent.parent.name == "yellow-doodle"
    assert yellow.data["logo_motion"]["spin"] == ["spark"] and {"telegram", "octopus", "spark"} <= set(
        yellow.logos()
    )
    assert yellow.data["sfx"]["kinetic"] == ["pop", 0.16] and yellow.data["sfx"]["beat"] == [
        "click-soft",
        0.16,
    ]
    assert packs.check(yellow) == []


@pytest.mark.parametrize("name", ["base", "yellow-doodle"])
def test_every_v1_type_renders(name, paths, monkeypatch):
    pk = packs.load(name, [packs.BUILTIN])
    src = paths.media / "proxy" / "B.mp4"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"x")
    monkeypatch.setattr(
        pages, "ffprobe_json", lambda f: {"streams": [{"codec_type": "video", "width": 1920, "height": 1080}]}
    )
    fields = {
        "label": LABEL,
        "chip": {"label": "l", "code": "npm i"},
        "kinetic": {"words": "كلمة ثانية", "highlight": ["ثانية"]},
        "big-number": {"word": "1.7M", "pre": "من"},
        "chapter": {"title": "t", "kicker": "k", "logo": "spark"},
        "doodle": {"scene": "flood", "beats": {"bot": "x"}},
        "screen": {"source": "B", "title": "T", "steps": ["one"]},
        "plug": {},
    }
    for t in V1:
        c = cue(f"c-{t}", t, fields[t], 10, 16, beats={"bot": 11.0})
        html = render(pl(c, 6, side="left", theme="dark", big=BIG), pk, env(paths, plug="P"))
        accent = pk.data["colors"]["accent"]
        if t in ("chapter", "big-number", "plug"):
            assert accent in html, (name, t)
    hand = render(pl(cue("d", "doodle", fields["doodle"], beats={"bot": 11.0}), 6), pk, env(paths))
    assert ("Aref Ruqaa" in hand) == (name == "yellow-doodle")


def test_overlapping_scenes_alternate_tracks_and_no_track_overlaps(paths, base):
    a = pl(
        cue("dd-broadcast", "doodle", {"scene": "flood", "beats": {"bot": "y"}}, 40, 47, beats={"bot": 41.0}),
        6,
    )
    b = pl(cue("ch-4", "chapter", {"title": "t", "kicker": "k", "logo": "spark"}, 46.5, 50), 6)
    c = pl(cue("ch-5", "chapter", {"title": "t", "kicker": "k", "logo": "spark"}, 50, 53), 6)
    r = write(paths, base, [pl(cue("intro", "label", LABEL), side="left", theme="dark"), a, b, c])
    by = {g.id: g for g in r.graphics}
    assert (by["dd-broadcast"].track, by["ch-4"].track, by["ch-5"].track) == (6, 5, 6)
    index = (paths.hf / "index.html").read_text()
    for t in {g.track for g in r.graphics}:
        spans = sorted((g.start, g.start + g.dur) for g in r.graphics if g.track == t)
        assert all(x[1] <= y[0] + 1e-6 for x, y in itertools.pairwise(spans)), t
    assert 'data-track-index="5"' in index


def test_rtl_languages_and_chip_default_logo_in_the_key(paths, base):
    p = pl(cue("intro", "label", LABEL), side="left", theme="dark")
    for lang, d in (("ar", "rtl"), ("fa", "rtl"), ("he", "rtl"), ("en", "ltr")):
        ctx = pages.base_context(p, base, env(paths, lang=lang))
        assert ctx["dir"] == d
    chip = pl(cue("c1", "chip", {"label": "l", "code": "x"}), side="left")
    k1 = pages.key(chip, base, env(paths))
    logo = paths.root / "spark.svg"
    logo.write_text("<svg/>")
    assert pages.key(chip, base, env(paths, logos={"spark": logo})) != k1


def test_frame_safe_duration_never_rounds_up_a_frame():
    """HyperFrames renders ceil(duration x fps) frames: 147.5667 s gave 8855 instead of 8854 in the fixture's
    4K chunk 3, one frame of picture behind the sound for the rest of the master."""
    import math

    from vedit.graphics.compose import frame_safe

    assert frame_safe(150.0) == "150.0000" and frame_safe(149.6) == "149.6000"  # exact: text unchanged
    for d in (147.5667, 790.3667, 597.1667 - 449.6, 12.3333):
        t = frame_safe(d)
        assert math.ceil(float(t) * 60) == round(d * 60), (d, t)
        assert abs(float(t) - d) < 1e-3
