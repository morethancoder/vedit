"""Specimen: the bundled sample cues (vedit/styles/specimen.yaml) rendered by the phase 04 engine for any pack.

Each tile is a cue with a fixed placement (no face track): `pages.render` makes its sub-composition and the
tiles play one after another over a neutral backdrop in a small HyperFrames project. The sheet project is
snapshotted at every tile's `snap` second; the clip project (`--clip`) is a ~10 s draft render of a few types.

    work: <config>/cache/specimens/_work/<pack>-<hash>/{hf-sheet,hf-clip,custom/plug,.vedit/media}
    out:  <pack>/specimen/ (draft, global, channel)  or  <config>/cache/specimens/<name>/ (built-in)
          specimen.png, specimen.mp4, tiles/<id>.png (960x540), key.json (content hash per output)

Incremental: an output is re-rendered only when the hash of its project files (and the pinned HyperFrames)
changed.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import yaml

from vedit.graphics import compose, pages
from vedit.graphics import pack as packs
from vedit.graphics.big import text_em
from vedit.graphics.cues import Cue
from vedit.graphics.plan import Placement
from vedit.project import Paths
from vedit.report import VeditError
from vedit.run import enc_h264, hash_of, run, sample_hash
from vedit.styleauthor.drafts import cache_root
from vedit.versions import HYPERFRAMES

SPEC = packs.BUILTIN / "specimen.yaml"
TILE = (960, 540)  # tile PNG size kept on disk
GAP = 0.4  # seconds of empty backdrop between tiles
SNAP_TIMEOUT, RENDER_TIMEOUT, MEDIA_TIMEOUT = 600, 900, 120
BACKDROP = {
    "dark": "radial-gradient(ellipse at 50% 42%, #3a3a40 0%, #1c1c20 58%, #0d0d0f 100%)",
    "light": "radial-gradient(ellipse at 50% 42%, #f6f4ee 0%, #e4e1d8 70%, #d2cec3 100%)",
}


@dataclass
class Tile:
    id: str
    type: str
    dur: float
    fields: dict
    snap: float | None = None
    side: str = "left"
    theme: str = "dark"
    bg: str = "dark"
    beats: dict = field(default_factory=dict)

    @property
    def at(self) -> float:
        return float(self.snap) if self.snap is not None else max(0.5, self.dur - 1.0)


@dataclass
class Built:
    hf: Path
    starts: dict[str, float]  # tile id -> program start
    tiles: list[Tile]
    problems: dict[str, str]  # tile id -> why it was left out
    key: str
    total: float


def load_spec(path: Path = SPEC) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def lang_of(pk) -> str:
    langs = [str(x) for x in pk.data.get("lang") or []]
    return langs[0] if langs else "ar"


def tiles(spec: dict, lang: str) -> list[Tile]:
    key = lang if lang in ("ar", "en") else "en"
    out = []
    for t in spec["tiles"]:
        f = t.get("fields") or {}
        out.append(
            Tile(
                t["id"],
                t["type"],
                float(t["dur"]),
                dict(f.get(key) or {}),
                t.get("snap"),
                t.get("side", "left"),
                t.get("theme", "dark"),
                t.get("bg", "dark"),
                dict(t.get("beats") or {}),
            )
        )
    return out


def clip_tiles(spec: dict, lang: str) -> list[Tile]:
    by = {t.id: t for t in tiles(spec, lang)}
    out = []
    for tid, d in (spec.get("clip") or {}).items():
        t = by[tid]
        t.dur, t.snap = float(d), None
        out.append(t)
    return out


def is_builtin(pk) -> bool:
    return pk.dirs[0].parent == packs.BUILTIN


def out_dir(pk) -> Path:
    return cache_root() / pk.name if is_builtin(pk) else pk.dirs[0] / "specimen"


def work_dir(pk) -> Path:
    return cache_root() / "_work" / f"{pk.name}-{hash_of(str(pk.dirs[0]))[:6]}"


SCREEN_BOXES = [  # x, y, w, h, colour: title bar, sidebar + items, heading, two lines, a panel, a moving block
    (0, 0, 1280, 54, "2a2d34"), (0, 54, 250, 746, "24262c"), (24, 90, 190, 18, "3a3e47"),
    (24, 130, 150, 18, "3a3e47"), (24, 170, 170, 18, "3a3e47"), (300, 100, 640, 28, "454a55"),
    (300, 150, 880, 16, "33363e"), (300, 180, 820, 16, "33363e"), (300, 240, 900, 420, "272a31"),
    ("'320+mod(t*110\\,780)'", 600, 80, 40, "6b7280"),
]  # fmt: skip


def _box(x, y, w, h, c) -> str:
    return f"drawbox=x={x}:y={y}:w={w}:h={h}:color=0x{c}:t=fill"


def screen_media(log: Path | None = None) -> Path:
    """A neutral 8 s 1280x800 clip standing in for a screen recording: grey app panels and one moving block,
    drawn by ffmpeg (no footage in the repo), made once, VideoToolbox encode."""
    f = cache_root() / "_media" / "screen-v2.mp4"
    if not f.is_file():
        f.parent.mkdir(parents=True, exist_ok=True)
        tmp = f.with_name("screen.tmp.mp4")
        src = ",".join(["color=c=0x1d1f24:s=1280x800:r=30:d=8", *(_box(*b) for b in SCREEN_BOXES)])
        run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", src, *enc_h264("2M"), str(tmp)],
            MEDIA_TIMEOUT,
            log=log,
        )
        tmp.replace(f)
    return f


# ---- the project ----


def big_of(pk, word: str) -> dict:
    """A fixed big-word layout: 240 px, centred, as if the head were in the middle."""
    adv, tr = pk.advances(), (pk.data.get("big") or {}).get("track", -0.03)
    fs = 240
    w = round(text_em(word, adv, tr) * fs)
    return {"side": "left", "fs": fs, "left": 960 - w // 2, "top": round(540 - 0.53 * fs), "width": w,
            "tuck": 0.0, "drift": 0}  # fmt: skip


def placement(pk, t: Tile, start: float) -> Placement:
    cue = Cue(t.id, t.type, pk.name, dict(t.fields), "S", start, start, start + t.dur, key=t.id)
    cue.beats = {name: start + float(s) for name, s in t.beats.items()}
    p = Placement(cue, start, t.dur, 1, t.side, t.theme, False)
    if t.type == "big-number":
        p.big = big_of(pk, str(t.fields.get("word", "")))
    return p


def index_html(pk, lang: str, graphics, sfx, bgs: list[tuple[float, float, str]], total: float) -> str:
    hosts = "\n".join(compose.host(g) for g in graphics)
    audio = "\n".join(
        f'      <audio id="sfx-{n}" src="assets/sfx/{name}.mp3" data-start="{t:.3f}" data-duration="{ln}" '
        f'data-track-index="{tr}" data-volume="{gain}"></audio>'
        for t, ln, name, gain, tr, n in sfx
    )
    sets = [
        f'      tl.set("#bg-light", {{ opacity: {1 if b == "light" else 0} }}, {s:.3f});' for s, _, b in bgs
    ]
    font = (pk.data.get("font") or {}).get("text", "sans-serif")
    return f"""<!doctype html>
<html lang="{lang}">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=1920, height=1080" />
    <script src="assets/gsap.min.js"></script>
    <style>
{pages.font_faces(pk)}
      * {{ margin: 0; padding: 0; box-sizing: border-box; }}
      html, body {{ margin: 0; width: 1920px; height: 1080px; overflow: hidden; background: #000; }}
      #root {{ position: relative; width: 100%; height: 100%; overflow: hidden; font-family: {font}; }}
      .bg {{ position: absolute; inset: 0; }}
      #bg-dark {{ background: {BACKDROP["dark"]}; }}
      #bg-light {{ background: {BACKDROP["light"]}; opacity: 0; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{total:.3f}" data-width="1920" data-height="1080">
      <div id="bg-dark" class="bg"></div>
      <div id="bg-light" class="bg"></div>
{hosts}
{audio}
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
{chr(10).join(sets)}
      window.__timelines["main"] = tl;
    </script>
  </body>
</html>
"""


def _files_key(hf: Path) -> str:
    parts: list = [HYPERFRAMES]
    for f in sorted(p for p in hf.rglob("*") if p.is_file() and ".hyperframes" not in p.parts):
        rel = str(f.relative_to(hf))
        parts += [rel, sample_hash(f) if f.is_symlink() or f.suffix in (".mp4", ".webm") else f]
    return hash_of(*parts)


def build(pk, mode: str = "sheet", spec: dict | None = None, log: Path | None = None) -> Built:
    """Write the specimen HyperFrames project of `pk` (mode sheet|clip) under its work dir."""
    spec = spec or load_spec()
    lang = lang_of(pk)
    ts = tiles(spec, lang) if mode == "sheet" else clip_tiles(spec, lang)
    work = work_dir(pk)
    hf = work / f"hf-{mode}"
    if hf.exists():
        shutil.rmtree(hf)
    (hf / "compositions").mkdir(parents=True)
    paths = Paths(work)
    plug = (spec.get("plug") or {}).get(lang if lang in ("ar", "en") else "en") or {}
    (paths.custom / "plug").mkdir(parents=True, exist_ok=True)
    (paths.custom / "plug" / "plug.yaml").write_text(
        yaml.safe_dump(plug, allow_unicode=True), encoding="utf-8"
    )
    env = pages.Env(paths, lang, None, None, "specimen", {})
    logos = pk.logos()
    graphics, media, starts, problems, bgs = [], {}, {}, {}, []
    kept: list[Tile] = []
    t0 = GAP
    for t in ts:
        try:
            if t.type == "screen":
                compose.link(screen_media(log), Path(paths.media) / "proxy" / f"{t.fields.get('source')}.mp4")
            errs = packs.check_fields(pk.template(t.type), t.fields, t.id, logos)
            if errs:
                raise VeditError("; ".join(errs))
            p = placement(pk, t, t0)
            pg = pages.render(p, pk, env)
        except VeditError as e:
            problems[t.id] = e.message
            continue
        (hf / "compositions" / f"{t.id}.html").write_text(pg.html, encoding="utf-8")
        media.update(pg.media)
        graphics.append(
            compose.Graphic(t.id, t.type, t0, t.dur, "front", 1, [(k, t0 + s) for k, s in pg.sounds])
        )
        starts[t.id] = t0
        bgs.append((t0 - GAP / 2, t0 + t.dur, t.bg))
        kept.append(t)
        t0 += t.dur + GAP
    total = round(t0, 3)
    sfx = compose.place_sfx(graphics, pk)
    compose.assets(hf, [pk], env, {r[2] for r in sfx})
    for rel, src in media.items():
        compose.link(src, hf / rel)
    for name, data in compose.PROJECT_FILES.items():
        (hf / name).write_text(json.dumps(data, indent=2) + "\n")
    (hf / "index.html").write_text(index_html(pk, lang, graphics, sfx, bgs, total), encoding="utf-8")
    return Built(hf, starts, kept, problems, hash_of(mode, _files_key(hf)), total)


# ---- rendering ----


def hf_cmd(sub: str, hf: Path, *extra: str) -> list[str]:
    return ["npx", "--yes", f"hyperframes@{HYPERFRAMES}", sub, str(hf), *extra]


def _keys(out: Path) -> dict:
    try:
        return json.loads((out / "key.json").read_text())
    except (OSError, ValueError):
        return {}


def _save_key(out: Path, what: str, key: str) -> None:
    keys = _keys(out)
    keys[what] = key
    (out / "key.json").write_text(json.dumps(keys, indent=1) + "\n")


def snapshot(b: Built, shots: Path, log: Path | None) -> dict[str, Path]:
    """One 1920x1080 PNG per tile at its snap second: tile id -> file."""
    shutil.rmtree(shots, ignore_errors=True)
    shots.mkdir(parents=True)
    at = {t.id: round(b.starts[t.id] + t.at, 2) for t in b.tiles}
    times = ",".join(f"{x:g}" for x in at.values())
    args = ["--at", times, "--no-end", "--keep", "--output", str(shots), "--describe", "false"]
    run(hf_cmd("snapshot", b.hf, *args), SNAP_TIMEOUT, cwd=b.hf, log=log)
    got = {}
    for f in shots.glob("at-*s.png"):
        try:
            got[float(f.stem[3:-1])] = f
        except ValueError:
            continue
    out = {}
    for tid, x in at.items():
        near = min(got, key=lambda s: abs(s - x), default=None)
        if near is not None and abs(near - x) < 0.01:
            out[tid] = got[near]
    return out


def sheet_tiles(pk, force: bool = False, log: Path | None = None) -> tuple[dict[str, Path], Built, bool]:
    """(tile id -> PNG in out/tiles/, the build, rendered now?) — reused when the project hash is unchanged."""
    b = build(pk, "sheet", log=log)
    out = out_dir(pk)
    tdir = out / "tiles"
    have = {t.id: tdir / f"{t.id}.png" for t in b.tiles}
    if not force and _keys(out).get("sheet") == b.key and all(f.is_file() for f in have.values()):
        return have, b, False
    shutil.rmtree(tdir, ignore_errors=True)
    tdir.mkdir(parents=True)
    shots = snapshot(b, work_dir(pk) / "shots", log)
    missing = [t.id for t in b.tiles if t.id not in shots]
    if missing:
        raise VeditError(f"hyperframes snapshot gave no frame for {', '.join(missing)}; see {log}")
    for tid, f in shots.items():
        img = cv2.imread(str(f))
        cv2.imwrite(str(have[tid]), cv2.resize(img, TILE, interpolation=cv2.INTER_AREA))
    _save_key(out, "sheet", b.key)
    return have, b, True


def clip(pk, force: bool = False, log: Path | None = None) -> tuple[Path, bool]:
    """out/specimen.mp4: a ~10 s 1080p draft render of the clip tiles (GPU encode)."""
    b = build(pk, "clip", log=log)
    out = out_dir(pk)
    f = out / "specimen.mp4"
    if not force and _keys(out).get("clip") == b.key and f.is_file():
        return f, False
    out.mkdir(parents=True, exist_ok=True)
    tmp = out / "specimen.tmp.mp4"
    run(hf_cmd("render", b.hf, "--quality", "draft", "--gpu", "--quiet", "--output", str(tmp)), RENDER_TIMEOUT,
        cwd=b.hf, log=log)  # fmt: skip
    if not tmp.is_file() or tmp.stat().st_size == 0:
        raise VeditError(f"hyperframes render wrote no clip; see {log}")
    tmp.replace(f)
    _save_key(out, "clip", b.key)
    return f, True
