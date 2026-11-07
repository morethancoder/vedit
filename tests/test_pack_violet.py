"""claude-violet: the Claude Code in Telegram video's look as a pack (phase 05 leaf feature-claude-violet)."""

import json
import re

import pytest

from vedit.graphics import pack as packs
from vedit.graphics import pages
from vedit.graphics.cues import Cue
from vedit.graphics.plan import Placement
from vedit.project import Paths

V1 = ["label", "chip", "kinetic", "big-number", "chapter", "doodle", "screen", "plug"]
BIG = {"side": "left", "fs": 240, "left": 300, "top": 260, "width": 500, "tuck": 0.45, "drift": 30}
FIELDS = {
    "label": {"logo": "spark", "kicker": "آخر الفيديو", "title": "مفاجأة لصنّاع المحتوى", "sub": "سطر"},
    "chip": {"label": "قل لأي ذكاء اصطناعي", "code": "اربط لي الـ MCP"},
    "kinetic": {"words": "«البوت شغال ✓»", "highlight": ["✓»"]},
    "big-number": {"word": "1.7M", "pre": "من 200 ألف إلى"},
    "chapter": {"title": "كيف بدأت", "kicker": "الجزء ١", "logo": "telegram"},
    "doodle": {"scene": "path", "beats": {"civil": "x", "code": "y"}},
    "screen": {"source": "B", "title": "بوتات", "steps": ["one", "two"]},
    "plug": {},
}


@pytest.fixture
def violet(tmp_path, monkeypatch):
    monkeypatch.setenv("VEDIT_CONFIG_DIR", str(tmp_path / "config"))  # never the real ~/.config/vedit
    return packs.load("claude-violet")


@pytest.fixture
def paths(tmp_path, monkeypatch):
    p = Paths(tmp_path / "proj")
    (p.root / ".vedit" / "program").mkdir(parents=True)
    src = p.media / "proxy" / "B.mp4"
    src.parent.mkdir(parents=True)
    src.write_bytes(b"x")
    monkeypatch.setattr(
        pages, "ffprobe_json", lambda f: {"streams": [{"codec_type": "video", "width": 1920, "height": 1080}]}
    )
    return p


def placement(cid, typ, fields, **kw):
    c = Cue(cid, typ, "claude-violet", fields, "A", 10.0, 10.0, 16.0, key=f"k-{cid}-{json.dumps(fields)}")
    c.beats = {"civil": 11.0, "code": 12.0}
    return Placement(c, 10.0, 6.0, 6, side="left", theme="dark", big=BIG, **kw)


def env(paths, lang="ar"):
    return pages.Env(paths, lang, None, "PowerTeleBot", "demo", {})


def test_pack_checks_clean_and_owns_every_v1_type(violet):
    assert packs.check(violet) == []
    own = violet.type_sources()
    assert all(own[t] == "claude-violet" for t in V1), own
    assert {"spark", "telegram"} <= set(violet.logos())
    assert all(violet.partials()[n].parent.parent.name == "claude-violet" for n in violet.partials())


def test_tokens_are_cs(violet):
    c, d = violet.data["colors"], violet.data
    assert (c["violet"], c["lilac"], c["ivory"]) == ("#7452E8", "#CDBEFF", "#FAF9F5")
    fams = {f["family"] for f in d["fonts"]}
    assert {"Source Serif 4", "DM Sans", "JetBrains Mono", "Caveat"} <= fams
    assert all(violet.file(f["file"]).parent.parent.name == "claude-violet" for f in d["fonts"])
    assert d["big"]["track"] == -0.04 and violet.advances()["B"] > 0  # C serif600-advances.json
    assert d["sfx"]["chip"] == ["key-press", 0.55] and d["sfx_files"]["key-press"] == 0.4
    assert d["logo_motion"]["spin"] == ["spark"]
    assert "rgba(10,6,20,.5)" in d["themes"]["dark"]["shadow"]


def test_arabic_fallback_in_every_stack(violet):
    fams = {f["family"] for f in violet.data["fonts"]}
    arabic = {"Noto Naskh Arabic", "IBM Plex Sans Arabic"} & fams
    assert arabic == {"Noto Naskh Arabic", "IBM Plex Sans Arabic"}
    for name, stack in violet.data["font"].items():
        assert any(a in stack for a in arabic), name
    assert violet.data["font"]["serif"].startswith('"Source Serif 4", "Noto Naskh Arabic"')


@pytest.mark.parametrize("typ", V1)
def test_every_v1_type_renders(violet, paths, typ):
    p = placement(f"c-{typ}", typ, FIELDS[typ])
    html = pages.render(p, violet, env(paths)).html
    assert "{{" not in html and "}}" not in html
    assert f'window.__timelines["{p.id}"]' in html and "const D = 6;" in html
    assert '"Noto Naskh Arabic"' in html and "noto-naskh-arabic-arabic-600-normal.woff2" in html
    assert "#FFD60A" not in html  # nothing of the yellow look leaks in from base
    if typ in ("label", "chip", "kinetic", "chapter"):
        assert 'dir="rtl"' in html


def test_spark_turns_and_keeps_drifting_like_c(violet, paths):
    html = pages.render(placement("l", "label", FIELDS["label"]), violet, env(paths)).html
    assert "rotation: -140, scale: 0.3" in html and "rotation: 40" in html
    assert 'fill="#C4B2FF"' in html  # the dark theme's spark lilac
    tg = pages.render(placement("ch", "chapter", FIELDS["chapter"]), violet, env(paths)).html
    assert 'fill="#7452E8"' in tg and "rotation: 40" not in tg  # violet telegram disc, no drift


def test_english_keeps_cs_serif_tracking(violet, paths):
    f = {"words": "Say I approve", "highlight": ["approve"]}
    html = pages.render(placement("k", "kinetic", f), violet, env(paths, lang="en")).html
    assert 'dir="ltr"' in html and "letter-spacing: -.025em" in html
    assert re.search(r"\.w\.hl \{[^}]*font-style: italic", html)
