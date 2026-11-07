"""Style authoring: palette, drafts (new/fork/pick/save), specimen project generation, sheets, the commands.

Never touches the real config (VEDIT_CONFIG_DIR -> tmp) and never runs HyperFrames (snapshot/render mocked).
"""

import json

import cv2
import numpy as np
import pytest
import yaml

from vedit.cli import main
from vedit.graphics import pack as packs
from vedit.graphics import pages
from vedit.report import VeditError
from vedit.styleauthor import drafts, palette, refs, sheet, specimen

RED, CREAM, NAVY, GREY = (230, 40, 30), (245, 240, 228), (16, 18, 40), (120, 120, 120)


def png(path, blocks, size=(90, 160)):
    """An image of vertical colour bands (RGB), one per block."""
    h, w = size
    img = np.zeros((h, w, 3), np.uint8)
    n = len(blocks)
    for i, rgb in enumerate(blocks):
        img[:, i * w // n : (i + 1) * w // n] = rgb[::-1]
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), img)
    return path


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    d = tmp_path / "cfg"
    monkeypatch.setenv("VEDIT_CONFIG_DIR", str(d))
    return d


@pytest.fixture
def refdir(tmp_path):
    d = tmp_path / "refs"
    png(d / "a.png", [GREY, RED, CREAM, NAVY])
    png(d / "b.png", [GREY, GREY, CREAM, NAVY])
    (d / "notes.txt").write_text("not an image")
    return d


@pytest.fixture
def no_render(monkeypatch, tmp_path):
    """Snapshot writes one plain frame per tile; the screen clip is a stub; ffprobe answers 1280x800."""
    calls = []

    def snap(b, shots, log):
        calls.append(b.hf)
        shots.mkdir(parents=True, exist_ok=True)
        out = {}
        for t in b.tiles:
            out[t.id] = shots / f"{t.id}.png"
            cv2.imwrite(str(out[t.id]), np.full((1080, 1920, 3), 40, np.uint8))
        return out

    stub = tmp_path / "screen.mp4"
    stub.write_bytes(b"stub")
    monkeypatch.setattr(specimen, "snapshot", snap)
    monkeypatch.setattr(specimen, "screen_media", lambda log=None: stub)
    probe = {"streams": [{"codec_type": "video", "width": 1280, "height": 800}]}
    monkeypatch.setattr(pages, "ffprobe_json", lambda f: probe)
    return calls


# ---- palette ----


def test_palette_finds_the_blocks_and_guesses(tmp_path):
    f = png(tmp_path / "x.png", [GREY, RED, CREAM, NAVY])
    cl = palette.extract([f], k=4)
    assert len(cl) == 4 and abs(sum(c.weight for c in cl) - 1) < 1e-6
    hexes = {c.hex for c in cl}
    for rgb in (RED, CREAM, NAVY, GREY):
        assert min(palette.delta_e(palette.hex_of(np.array(rgb) / 255), h) for h in hexes) < 2
    g = palette.guess(cl)
    assert palette.delta_e(g["accent"], "#E6281E") < 2  # the saturated red
    assert palette.delta_e(g["ivory"], "#F5F0E4") < 2 and palette.delta_e(g["ink"], "#101228") < 2


def test_palette_keeps_base_ivory_when_lightest_is_not_light(tmp_path):
    f = png(tmp_path / "x.png", [GREY, (176, 125, 115), NAVY])
    g = palette.guess(palette.extract([f], k=3))
    assert "ivory" not in g and "ink" in g


def test_palette_accent_is_a_small_violet_not_the_grey_background(tmp_path):
    img = np.full((160, 90, 3), 120, np.uint8)  # grey background, 99% of the pixels
    img[10:24, 10:24] = (200, 60, 150)  # a small violet patch (BGR), ~1.4%
    f = tmp_path / "g.png"
    cv2.imwrite(str(f), img)
    cl = palette.extract([f])
    assert all(c.weight >= palette.MIN_WEIGHT for c in cl)
    g = palette.guess(cl)
    assert palette.delta_e(g["accent"], "#963CC8") < 4
    d = palette.distance({"accent": g["accent"], "bg": "#787878"}, cl)
    assert d["per"]["accent"]["de"] < 4 and d["per"]["bg"]["de"] < 4
    grey_only = png(tmp_path / "h.png", [GREY, CREAM])
    assert "accent" not in palette.guess(palette.extract([grey_only]))


def test_palette_distance():
    cl = [
        palette.Cluster("#FF0000", 0.5, tuple(palette.lab_of_hex("#FF0000"))),
        palette.Cluster("#000000", 0.5, (0, 0, 0)),
    ]
    d = palette.distance(
        {"accent": "#FF0000", "ink": "#000000", "ref1": "#123456", "rgba": "rgba(0,0,0,1)"}, cl
    )
    assert d["mean"] == 0.0 and set(d["per"]) == {"accent", "ink"}
    assert palette.distance({"accent": "#FFFFFF"}, cl)["mean"] == 100.0
    assert palette.distance({"accent": "#FFFFFF"}, []) is None


def test_spread_picks_evenly():
    assert refs.spread([1, 2, 3], 8) == [1, 2, 3]
    assert refs.spread(list(range(100)), 3) == [0, 50, 99]


# ---- drafts ----


def test_set_key_keeps_comments_and_blocks():
    text = "# head\nname: base\ncolors:\n  accent: '#111111'\n  ink: '#000000'\n\n# themes\nthemes: {}\n"
    out = drafts.set_key(text, "colors", {"accent": "#FFD60A"})
    assert "# head" in out and "# themes" in out and "ink" not in out
    assert yaml.safe_load(out)["colors"] == {"accent": "#FFD60A"}
    out = drafts.set_key(out, "extends", "base", after="name")
    assert out.splitlines()[2] == "extends: base"


def test_new_from_dir_of_pngs(cfg, refdir):
    res = drafts.new("warm-test", refdir, "en")
    d = cfg / "styles" / "drafts" / "warm-test"
    assert res["path"] == str(d)
    assert sorted(p.name for p in (d / "refs").iterdir()) == ["a.png", "b.png"]
    for f in ("brief.md", "history.md", "palette.json", "types/label.html", "partials/base.html"):
        assert (d / f).is_file(), f
    assert (d / "fonts").is_dir() and (d / "doodle.yaml").is_file()  # for the pack's own files / doodle look
    assert not any(line.strip() == "-" for line in (d / "brief.md").read_text().splitlines())
    assert (
        packs.load("warm-test", drafts.roots()).data["font"]["ui"] == packs.load("base").data["font"]["text"]
    )
    raw = packs.read_yaml(d)
    assert raw["name"] == "warm-test" and raw["extends"] == "base" and raw["lang"] == ["en"]
    assert palette.delta_e(raw["colors"]["accent"], "#E6281E") < 3
    assert any(k.startswith("ref") for k in raw["colors"])
    assert raw["themes"]["dark"]["kicker"] == raw["colors"]["accent"]  # themes follow the new accent
    pk = packs.load("warm-test", drafts.roots())
    assert packs.check(pk) == []
    assert "refs/a.png" in (d / "brief.md").read_text()
    with pytest.raises(VeditError):
        drafts.new("warm-test", refdir, None)
    with pytest.raises(VeditError):
        drafts.new("Bad Name", refdir, None)


def test_new_needs_images(cfg, tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(VeditError, match="no images"):
        drafts.new("x", tmp_path / "empty", None)
    assert not (cfg / "styles" / "drafts" / "x").exists()


def test_fork_pick_save(cfg, refdir):
    drafts.new("look", refdir, None)
    a = drafts.fork("look", "bold")
    drafts.fork("look", "calm")
    assert packs.read_yaml(a)["name"] == "look@bold"
    assert drafts.options("look") == ["look", "look@bold", "look@calm"]
    assert packs.check(packs.load("look@bold", drafts.roots())) == []
    pk = packs.load("look", drafts.roots())
    with pytest.raises(VeditError, match="still has options"):
        drafts.save("look", pk, packs.user_root(), [], False)
    with pytest.raises(VeditError, match="reason"):
        drafts.pick("look", "bold", "  ")
    res = drafts.pick("look", "bold", "the heavier kicker reads at phone size")
    d = cfg / "styles" / "drafts" / "look"
    assert res["kept"] == str(d) and sorted(res["over"]) == ["look", "look@calm"]
    assert drafts.options("look") == ["look"]
    assert packs.read_yaml(d)["name"] == "look"
    assert len(list((cfg / "styles" / "drafts" / ".archive").iterdir())) == 2
    hist = (d / "history.md").read_text()
    assert "picked 'bold'" in hist and "over: main, calm" in hist and "phone size" in hist
    pk = packs.load("look", drafts.roots())
    out = drafts.save("look", pk, packs.user_root(), ["warm", "bold"], False)
    g = cfg / "styles" / "look"
    assert out["path"] == str(g) and not d.exists()
    assert packs.read_yaml(g)["keywords"] == ["warm", "bold"]
    for f in ("refs/a.png", "brief.md", "history.md"):
        assert (g / f).is_file()
    assert "look" in [n for n, _, _ in packs.available()]


def test_save_refuses_problems_and_replacing(cfg, refdir):
    drafts.new("p", refdir, None)
    d = cfg / "styles" / "drafts" / "p"
    (d / "pack.yaml").write_text((d / "pack.yaml").read_text() + "colours: {}\n")
    with pytest.raises(VeditError, match="problem"):
        drafts.save("p", packs.load("p", drafts.roots()), packs.user_root(), [], False)
    (d / "pack.yaml").write_text((d / "pack.yaml").read_text().replace("colours: {}\n", ""))
    (cfg / "styles" / "p").mkdir(parents=True)
    with pytest.raises(VeditError, match="saving replaces it"):
        drafts.save("p", packs.load("p", drafts.roots()), packs.user_root(), [], False)
    out = drafts.save("p", packs.load("p", drafts.roots()), packs.user_root(), [], True)
    assert out["replaced"] and (cfg / "styles" / "p" / "pack.yaml").is_file()


def test_pick_main_keeps_the_draft(cfg, refdir):
    drafts.new("m", refdir, None)
    drafts.fork("m", "alt")
    drafts.pick("m", "main", "the original was calmer")
    assert (
        drafts.options("m") == ["m"] and "picked 'main'" in (drafts.draft_dir("m") / "history.md").read_text()
    )


# ---- specimen ----


@pytest.mark.parametrize("name", ["base", "yellow-doodle", "claude-violet"])
def test_specimen_project_for_builtin_packs(name, cfg, no_render):
    pk = packs.load(name, drafts.roots())
    b = specimen.build(pk, "sheet")
    ids = [t["id"] for t in specimen.load_spec()["tiles"]]
    assert b.problems == {} and [t.id for t in b.tiles] == ids
    assert b.hf.is_relative_to(cfg / "cache" / "specimens" / "_work")
    html = (b.hf / "index.html").read_text()
    for tid in ids:
        assert (b.hf / "compositions" / f"{tid}.html").is_file()
        assert f'data-composition-src="compositions/{tid}.html"' in html
    assert (b.hf / "assets" / "gsap.min.js").is_file() and (b.hf / "media" / "src-specimen.mp4").is_symlink()
    lang = specimen.lang_of(pk)
    label = (b.hf / "compositions" / "label.html").read_text()
    assert ("فتحت قناتي" in label) == (lang == "ar") and ("first channel" in label) == (lang == "en")
    starts = list(b.starts.values())
    assert starts == sorted(starts) and b.total > starts[-1]
    assert specimen.build(pk, "sheet").key == b.key  # same files, same key
    c = specimen.build(pk, "clip")
    assert [t.id for t in c.tiles] == list(specimen.load_spec()["clip"]) and 9 < c.total < 15


def test_specimen_tile_with_bad_fields_is_reported(cfg, no_render):
    pk = packs.load("base", drafts.roots())
    spec = specimen.load_spec()
    spec["tiles"][0]["fields"]["ar"]["oops"] = "x"
    b = specimen.build(pk, "sheet", spec)
    assert "unknown field 'oops'" in b.problems["label"] and "label" not in b.starts


def test_specimen_out_dirs(cfg, refdir):
    assert specimen.out_dir(packs.load("base")) == cfg / "cache" / "specimens" / "base"
    drafts.new("o", refdir, None)
    assert specimen.out_dir(packs.load("o", drafts.roots())) == drafts.draft_dir("o") / "specimen"


# ---- sheets ----


def test_compare_sheet_layout(tmp_path):
    a = png(tmp_path / "a.png", [RED], (540, 960))
    rows = [("one", {"label": (a, ""), "chip": (a, "")}), ("two", {"label": (None, "broken template")})]
    out = sheet.compare(rows, ["label", "chip"], tmp_path / "c.png")
    img = cv2.imread(str(out))
    w, h, pad, label_w = 640, 360, 16, 200
    assert img.shape[1] == label_w + 2 * (w + pad) + pad
    assert img.shape[0] == 90 + 2 * (h + 40 + 2 * pad)


def test_specimen_sheet_has_refs_column(tmp_path):
    a = png(tmp_path / "a.png", [RED], (540, 960))
    tiles = [("label", a, ""), ("chip", None, "why"), ("kinetic", a, "")]
    out = sheet.specimen("x", tiles, [a], [("accent", "#FF0000")], [("50%", "#000000")], tmp_path / "s.png")
    assert cv2.imread(str(out)).shape[1] == 3 * (640 + 16) + 16 + 552


# ---- commands ----


def run_json(capsys, *argv):
    code = main([*argv, "--json"])
    return code, json.loads(capsys.readouterr().out)


def test_style_commands_end_to_end(cfg, refdir, no_render, capsys, monkeypatch):
    code, out = run_json(capsys, "style", "new", "loop", "--from", str(refdir), "--lang", "ar")
    assert code == 0 and out["next"].endswith("vedit style try loop")
    code, out = run_json(capsys, "style", "try", "loop")
    assert code == 0, out
    d = out["data"]
    assert d["specimen"] == str(drafts.draft_dir("loop") / "specimen" / "specimen.png")
    assert len(d["tiles"]) == 9 and d["palette"]["mean"] >= 0 and d["clip"] is None
    assert len(no_render) == 1
    run_json(capsys, "style", "try", "loop")
    assert len(no_render) == 1  # nothing changed: not rendered again
    code, out = run_json(capsys, "style", "fork", "loop", "b")
    assert code == 0 and out["data"]["name"] == "loop@b"
    opened = []
    monkeypatch.setattr("vedit.commands.style.sh", lambda cmd, *a, **k: opened.append(cmd))
    code, out = run_json(capsys, "style", "compare", "loop", "--no-open")
    assert code == 0 and not opened
    assert out["data"]["sheet"].endswith("compare/loop+loop@b.png") and "pick loop" in out["next"]
    code, out = run_json(capsys, "style", "pick", "loop", "b", "--why", "bolder")
    assert code == 0
    code, out = run_json(capsys, "style", "save", "loop", "--channel", "ali-talks", "--keywords", "warm, red")
    assert code == 0 and out["data"]["path"] == str(cfg / "channels" / "ali-talks" / "styles" / "loop")
    code, out = run_json(capsys, "style", "save", "loop")
    assert code != 0


def test_style_try_builtin_writes_to_cache_not_package(cfg, no_render, capsys):
    code, out = run_json(capsys, "style", "try", "yellow-doodle")
    assert code == 0
    assert out["data"]["specimen"] == str(cfg / "cache" / "specimens" / "yellow-doodle" / "specimen.png")
    assert out["data"]["palette"] is None
    assert not (packs.BUILTIN / "yellow-doodle" / "specimen").exists()


def test_style_usage_errors(cfg, capsys):
    assert main(["style", "try"]) == 2
    assert main(["style", "new", "x"]) == 2
    assert main(["style", "compare", "base"]) == 2
