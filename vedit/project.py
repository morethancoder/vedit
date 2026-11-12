"""Load and validate project.yaml, find a project from any subfolder, and name every project path."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from vedit.recording import Trim

PROJECT_FILE = "project.yaml"
LANGS = ("ar", "en")
KEYS = {
    "slug",
    "lang",
    "dialect",
    "channel",
    "style",
    "accent",
    "hint",
    "sources",
    "logos",
    "plug",
    "outputs",
}
REQUIRED = ("slug", "lang", "sources")
SOURCE_KEYS = {"file", "camera", "trims", "fps", "mirror", "origin", "importer", "punch"}
OUTPUT_KINDS = ("master", "clip", "short", "story", "post")
OUTPUT_KEYS = {"id", "kind", "aspect", "platforms", "range", "captions", "fill"}
FILLS = ("plain", "blur")  # behind full-frame scenes in an output; never blur by default
RANGE_KEYS = {"from", "to", "near"}
CAPTIONS = ("burned", "srt", "none")
DEFAULT_PLATFORMS = {"master": ["youtube"], "clip": ["instagram-reels", "tiktok", "youtube-shorts"],
                     "short": ["instagram-reels", "tiktok", "youtube-shorts"], "story": ["instagram-stories"],
                     "post": ["instagram-feed"]}  # fmt: skip
DEFAULT_ASPECT = {"master": "16:9", "clip": "9:16", "short": "9:16", "story": "9:16", "post": "4:5"}
VEDIT_DIRS = ("media", "studio", "words", "edl", "program", "mattes", "hf", "renders", "logs")


class ProjectError(Exception):
    """A project.yaml problem; the message names the file, the key and what to do."""


@dataclass
class Source:
    """One recording. `file` is the edited video (picture and audio). `camera` (optional) is a clean camera
    recording, laid on `trims` ([track, start, end] in seconds, end to end = the edit) with `file`'s audio.
    `origin`/`importer`: the recorder project it came from and the importer plugin that read it."""

    name: str
    file: Path
    camera: list[Path] = field(default_factory=list)
    trims: list[Trim] | None = None
    fps: int | None = None
    mirror: bool = False
    origin: Path | None = None
    importer: str | None = None
    punch: bool | None = None

    @property
    def path(self) -> Path:
        return self.file

    @property
    def punch_in(self) -> bool:
        """Punch in on alternate jump cuts: on for camera sources unless `punch: false`; `punch: true` for others."""
        return self.punch if self.punch is not None else bool(self.camera)


@dataclass
class Output:
    """One thing the project produces: the YouTube master, a clip cut from it, a short, a story set, a feed post."""

    id: str
    kind: str = "master"
    aspect: str = "16:9"
    platforms: list[str] = field(default_factory=lambda: ["youtube"])
    range: dict | None = None  # clips: {"from": words, "to": words, "near": "A 245"}
    captions: str = "srt"
    fill: str = "plain"

    @property
    def vertical(self) -> bool:
        return self.aspect != "16:9"

    def as_dict(self) -> dict:
        d = {"id": self.id, "kind": self.kind, "aspect": self.aspect, "platforms": list(self.platforms)}
        if self.range:
            d["range"] = dict(self.range)
        d["captions"] = self.captions
        if self.fill != "plain":
            d["fill"] = self.fill
        return d


def default_outputs() -> list[Output]:
    """A project without `outputs:` makes exactly what vedit always made: one 16:9 YouTube master."""
    return [Output("youtube")]


def parse_outputs(raw, fname: Path | str) -> list[Output]:
    from vedit import formats as fm
    from vedit.report import VeditError

    if raw is None:
        return default_outputs()
    if not isinstance(raw, list) or not raw:
        raise ProjectError(f"{fname}: 'outputs' must be a list of outputs (see vedit guide outputs).")
    out: list[Output] = []
    for n, spec in enumerate(raw):
        where = f"outputs[{n}]"
        if not isinstance(spec, dict):
            raise ProjectError(f"{fname}: {where} must be a mapping with id, kind, aspect, platforms.")
        for k in spec:
            if k not in OUTPUT_KEYS:
                raise ProjectError(f"{fname}: unknown key '{k}' in {where}.{_suggest(k, OUTPUT_KEYS)}")
        oid = spec.get("id")
        if not isinstance(oid, str) or not re.match(r"^[a-z0-9][a-z0-9-]*$", oid):
            raise ProjectError(f"{fname}: {where}.id must be lowercase letters, digits and - (e.g. reel-1).")
        if oid in {o.id for o in out}:
            raise ProjectError(f"{fname}: two outputs are called '{oid}'. Give each a different id.")
        kind = spec.get("kind", "master" if not out else "clip")
        if kind not in OUTPUT_KINDS:
            raise ProjectError(f"{fname}: {where}.kind is '{kind}'; use one of: {', '.join(OUTPUT_KINDS)}.")
        aspect = str(spec.get("aspect", DEFAULT_ASPECT[kind]))
        if aspect not in fm.ASPECTS:
            raise ProjectError(f"{fname}: {where}.aspect is '{aspect}'; use one of: {', '.join(fm.ASPECTS)}.")
        plats = spec.get("platforms", DEFAULT_PLATFORMS[kind])
        if isinstance(plats, str):
            plats = [plats]
        if not isinstance(plats, list) or not all(isinstance(p, str) for p in plats):
            raise ProjectError(f"{fname}: {where}.platforms must be a list like [instagram-reels, tiktok].")
        for p in plats:
            try:
                pa = fm.platform(p)["aspect"]
            except VeditError as e:
                raise ProjectError(f"{fname}: {where}.platforms: {e.message}") from e
            if fm.ratio(pa) != fm.ratio(aspect) and aspect not in fm.platform(p)["aspects"]:
                raise ProjectError(
                    f"{fname}: {where} is {aspect} but {p} shows {pa}. Drop {p} or change the aspect."
                )
        rng = spec.get("range")
        if kind == "story" and rng is not None:
            if not isinstance(rng, dict) or not rng.get("from") or not rng.get("to"):
                raise ProjectError(f"{fname}: {where}.range needs from and to (words).")
            rng = {k: str(v) for k, v in rng.items()}
        elif kind == "clip":
            if not isinstance(rng, dict) or not rng.get("from") or not rng.get("to"):
                raise ProjectError(
                    f'{fname}: {where} is a clip: add range: {{from: "first words", to: "last words", near: A 245}}.'
                )
            for k in rng:
                if k not in RANGE_KEYS:
                    raise ProjectError(
                        f"{fname}: unknown key '{k}' in {where}.range.{_suggest(k, RANGE_KEYS)}"
                    )
            rng = {k: str(v) for k, v in rng.items()}
        elif rng is not None:
            raise ProjectError(
                f"{fname}: {where}.range is only for clips and stories (a {kind} uses the whole cut)."
            )
        caps = spec.get("captions", "srt" if kind == "master" else "burned")
        if caps not in CAPTIONS:
            raise ProjectError(f"{fname}: {where}.captions is '{caps}'; use one of: {', '.join(CAPTIONS)}.")
        fill = spec.get("fill", "plain")
        if fill not in FILLS:
            raise ProjectError(f"{fname}: {where}.fill is '{fill}'; use one of: {', '.join(FILLS)}.")
        out.append(Output(oid, kind, aspect, list(plats), rng, caps, fill))
    return out


@dataclass
class Paths:
    root: Path

    @property
    def project_yaml(self) -> Path:
        return self.root / PROJECT_FILE

    @property
    def src(self) -> Path:
        return self.root / "src"

    @property
    def summary(self) -> Path:
        return self.root / "summary.md"

    @property
    def cuts(self) -> Path:
        return self.root / "cuts.yaml"

    @property
    def cues(self) -> Path:
        return self.root / "cues.yaml"

    @property
    def custom(self) -> Path:
        return self.root / "custom"

    @property
    def vedit(self) -> Path:
        return self.root / ".vedit"

    @property
    def media(self) -> Path:
        return self.vedit / "media"

    @property
    def studio(self) -> Path:
        return self.vedit / "studio"

    @property
    def words(self) -> Path:
        return self.vedit / "words"

    @property
    def edl(self) -> Path:
        return self.vedit / "edl"

    @property
    def program(self) -> Path:
        return self.vedit / "program"

    @property
    def mattes(self) -> Path:
        return self.vedit / "mattes"

    @property
    def hf(self) -> Path:
        return self.vedit / "hf"

    @property
    def renders(self) -> Path:
        return self.vedit / "renders"

    @property
    def faces(self) -> Path:
        return self.vedit / "faces"

    @property
    def logs(self) -> Path:
        return self.vedit / "logs"

    @property
    def state(self) -> Path:
        return self.vedit / "state.json"

    def vedit_dirs(self) -> list[Path]:
        return [getattr(self, n) for n in VEDIT_DIRS]

    def ensure(self) -> None:
        """Create the .vedit/ folders (loading never does)."""
        for d in self.vedit_dirs():
            d.mkdir(parents=True, exist_ok=True)


@dataclass
class Project:
    root: Path
    slug: str
    lang: str
    sources: dict[str, Source]
    dialect: str | None = None
    channel: str | None = None
    style: str | None = None
    accent: str | None = None
    hint: str | None = None
    logos: list[str] = field(default_factory=list)
    plug: str | None = None
    outputs: list[Output] = field(default_factory=default_outputs)

    @property
    def paths(self) -> Paths:
        return Paths(self.root)

    @classmethod
    def load(cls, root: Path | str) -> Project:
        return load_project(Path(root))


def _suggest(key: str, valid) -> str:
    near = difflib.get_close_matches(str(key), sorted(valid), n=1)
    return f" Did you mean '{near[0]}'?" if near else f" Valid keys: {', '.join(sorted(valid))}."


def _str(where: str, data: dict, key: str, fname: Path) -> str | None:
    v = data.get(key)
    if v is None:
        return None
    if not isinstance(v, str):
        raise ProjectError(
            f"{fname}: '{key}' must be a string, got {type(v).__name__}{where}. Fix the value."
        )
    return v


def _path(f: Path, where: str, v, root: Path) -> Path:
    if not isinstance(v, str) or not v:
        raise ProjectError(f"{f}: {where} must be a path string.")
    p = _resolve(v, root)
    if not p.exists():
        raise ProjectError(
            f"{f}: {where} points to {p}, which does not exist. Fix the path (relative paths start at the project folder)."
        )
    return p


def _source(name: str, spec, f: Path, root: Path) -> Source:
    where = f"sources.{name}"
    if not isinstance(spec, dict):
        raise ProjectError(f"{f}: {where} must be a mapping like {{ file: src/A.mp4 }}.")
    for k in spec:
        if k not in SOURCE_KEYS:
            raise ProjectError(f"{f}: unknown key '{k}' in {where}.{_suggest(k, SOURCE_KEYS)}")
    if "file" not in spec:
        raise ProjectError(f"{f}: {where} needs 'file' (the edited video).")
    src = Source(name=name, file=_path(f, f"{where}.file", spec["file"], root))
    cam = spec.get("camera")
    if cam is not None:
        cams = [cam] if isinstance(cam, str) else cam
        if not isinstance(cams, list) or not cams:
            raise ProjectError(f"{f}: {where}.camera must be a path or a list of paths (one per track).")
        src.camera = [_path(f, f"{where}.camera", c, root) for c in cams]
    if spec.get("trims") is not None:
        if not src.camera:
            raise ProjectError(
                f"{f}: {where}.trims needs a camera: they say which parts of it make the edit."
            )
        trims = spec["trims"]
        ok = isinstance(trims, list) and trims and all(
            isinstance(t, list) and len(t) == 3 and isinstance(t[0], int)
            and all(isinstance(x, (int, float)) for x in t[1:]) and t[2] > t[1]
            for t in trims
        )  # fmt: skip
        if not ok:
            raise ProjectError(
                f"{f}: {where}.trims must be a list of [track, start, end] (seconds, end > start)."
            )
        if any(not 0 <= t[0] < len(src.camera) for t in trims):
            raise ProjectError(f"{f}: {where}.trims names a track with no camera file (tracks count from 0).")
        src.trims = [Trim(int(t[0]), float(t[1]), float(t[2])) for t in trims]
    fps = spec.get("fps")
    if fps is not None and (not isinstance(fps, int) or isinstance(fps, bool) or fps <= 0):
        raise ProjectError(f"{f}: {where}.fps must be a whole number of frames per second.")
    src.fps = fps
    for k in ("mirror", "punch"):
        if spec.get(k) is not None and not isinstance(spec[k], bool):
            raise ProjectError(f"{f}: {where}.{k} must be true or false.")
    src.mirror = bool(spec.get("mirror", False))
    src.punch = spec.get("punch")
    if spec.get("origin") is not None:
        o = spec["origin"]
        if not isinstance(o, str) or not o:
            raise ProjectError(f"{f}: {where}.origin must be a path string.")
        src.origin = _resolve(o, root)  # may be gone after a clean; only `clean` reads it
    if spec.get("importer") is not None and not isinstance(spec["importer"], str):
        raise ProjectError(f"{f}: {where}.importer must be an importer name.")
    src.importer = spec.get("importer")
    return src


def _resolve(raw: str, root: Path) -> Path:
    p = Path(raw).expanduser()
    return p if p.is_absolute() else (root / p).resolve()


def load_project(root: Path) -> Project:
    root = root.expanduser().resolve()
    f = root / PROJECT_FILE
    if not f.is_file():
        raise ProjectError(f"{f}: file not found. Run vedit new <video> or pass --project PATH.")
    try:
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ProjectError(f"{f}: not valid YAML ({e}). Fix the syntax.") from e
    if not isinstance(data, dict):
        raise ProjectError(f"{f}: top level must be a mapping of keys (slug, lang, sources, ...).")

    for k in data:
        if k not in KEYS:
            raise ProjectError(f"{f}: unknown key '{k}'.{_suggest(k, KEYS)}")
    for k in REQUIRED:
        if data.get(k) in (None, "", {}):
            raise ProjectError(f"{f}: missing required key '{k}'. Add it (required: {', '.join(REQUIRED)}).")

    for k in ("slug", "lang", "dialect", "channel", "style", "accent", "hint", "plug"):
        _str("", data, k, f)
    if data.get("accent") is not None and not re.match(
        r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$", data["accent"]
    ):
        raise ProjectError(f"{f}: 'accent' is '{data['accent']}'; use a hex colour like #FFD60A.")
    lang = data["lang"]
    if lang not in LANGS:
        raise ProjectError(f"{f}: 'lang' is '{lang}'; use one of: {', '.join(LANGS)}.")
    logos = data.get("logos") or []
    if not isinstance(logos, list) or not all(isinstance(x, str) for x in logos):
        raise ProjectError(f"{f}: 'logos' must be a list of names, e.g. [telegram, mylogo].")

    raw_sources = data["sources"]
    if not isinstance(raw_sources, dict):
        raise ProjectError(f"{f}: 'sources' must be a mapping like A: {{ file: src/a.mov }}.")
    sources: dict[str, Source] = {}
    for name, spec in raw_sources.items():
        sources[str(name)] = _source(str(name), spec, f, root)

    return Project(
        root=root,
        slug=data["slug"],
        lang=lang,
        sources=sources,
        dialect=data.get("dialect"),
        channel=data.get("channel"),
        style=data.get("style"),
        accent=data.get("accent"),
        hint=data.get("hint"),
        logos=list(logos),
        plug=data.get("plug"),
        outputs=parse_outputs(data.get("outputs"), f),
    )


def find_project(start: Path | None = None, override: str | None = None) -> Path:
    """Project folder: --project PATH wins; else walk up from start (default cwd) to a project.yaml."""
    if override:
        p = Path(override).expanduser().resolve()
        if not (p / PROJECT_FILE).is_file():
            raise ProjectError(
                f"{p / PROJECT_FILE}: not found. Pass --project with a folder holding project.yaml."
            )
        return p
    cwd = (start or Path.cwd()).resolve()
    for d in (cwd, *cwd.parents):
        if (d / PROJECT_FILE).is_file():
            return d
    raise ProjectError(
        f"no {PROJECT_FILE} found from {cwd} up — run vedit new <video> or pass --project PATH"
    )
