"""Where drafts live and the file moves of the authoring loop: new, fork, pick, save.

    <config>/styles/drafts/<name>/            a draft (extends base; own pack.yaml, types/, partials/)
    <config>/styles/drafts/<name>@<variant>/  an option forked from it (pack name `<name>@<variant>`)
    <config>/styles/drafts/.archive/          options not picked, and packs a save replaced (dated)
    <config>/cache/specimens/                 specimens of built-in packs, and every pack's render work dirs

A draft keeps `refs/`, `palette.json` (the k-means clusters), `brief.md`, `history.md` and `specimen/`; save
carries them to the saved pack. pack.yaml is edited as text (one top-level line per key) so its comments stay.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import shutil
from pathlib import Path

import yaml

from vedit.channel import config_dir
from vedit.graphics import pack as packs
from vedit.report import VeditError
from vedit.styleauthor import palette

NAME = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SEP = "@"  # <name>@<variant>
MAIN = "main"  # the variant that means the draft itself (`vedit style pick foo main`)
COPY = ("types", "partials")  # what a new draft copies from base to edit; fonts/sfx/logos are inherited
FONTS = "fonts"  # a new draft gets an empty fonts/ for the files its `fonts:` list names
DOODLE = "doodle.yaml"  # base's doodle look, copied so the draft can change it


def drafts_root() -> Path:
    return packs.user_root() / packs.DRAFTS


def archive_root() -> Path:
    return drafts_root() / ".archive"


def cache_root() -> Path:
    return config_dir() / "cache" / "specimens"


def roots(channel: str | None = None) -> list[Path]:
    """Where `vedit style` resolves a name: drafts first, then the channel's, global, built-in."""
    return [drafts_root(), *packs.pack_roots(channel)]


def check_name(name: str, what: str = "style name") -> str:
    if not NAME.match(name or ""):
        raise VeditError(f"{what} {name!r}: use lowercase letters, digits and - (e.g. warm-hand)", exit=2)
    return name


def draft_dir(name: str) -> Path:
    return drafts_root() / name


def option(name: str, variant: str) -> str:
    return name if variant == MAIN else f"{name}{SEP}{variant}"


def options(name: str) -> list[str]:
    """The draft and its forks that exist, the draft first."""
    d = drafts_root()
    out = [name] if (d / name / "pack.yaml").is_file() else []
    if d.is_dir():
        out += sorted(f.parent.name for f in d.glob(f"{name}{SEP}*/pack.yaml"))
    return out


# ---- pack.yaml as text ----


def set_key(text: str, key: str, value, after: str | None = None) -> str:
    """Replace the top-level `key:` (and its indented block) with `value` (a mapping as an indented block of
    one-line values, anything else one flow line); a missing key goes after top-level key `after`, else last."""

    def flow(v) -> str:
        return (
            yaml.safe_dump(v, default_flow_style=True, allow_unicode=True, width=10**6)
            .strip()
            .removesuffix("\n...")
        )

    if isinstance(value, dict):
        line = f"{key}:\n" + "\n".join(f"  {flow(k)}: {flow(v)}" for k, v in value.items())
    else:
        line = f"{key}: {flow(value)}"
    pat = re.compile(rf"^{re.escape(key)}:.*\n(?:[ \t]+\S.*\n|[ \t]*\n(?=[ \t]+\S))*", re.MULTILINE)
    if pat.search(text):
        return pat.sub(lambda _: line + "\n", text, count=1)
    m = re.search(rf"^{re.escape(after)}:.*\n", text, re.MULTILINE) if after else None
    if m:
        return text[: m.end()] + line + "\n" + text[m.end() :]
    return text.rstrip("\n") + "\n" + line + "\n"


def recolor(text: str, old: dict, new: dict) -> str:
    """Every `old[k]` hex in the text becomes `new[k]` (themes follow the new accent, ivory, ink)."""
    for k, v in new.items():
        if old.get(k):
            text = re.sub(re.escape(str(old[k])), v, text, flags=re.IGNORECASE)
    return text


def write_yaml(d: Path, text: str) -> None:
    yaml.safe_load(text)  # a broken edit fails here, not at the next load
    (d / "pack.yaml").write_text(text, encoding="utf-8")


# ---- new ----

BRIEF = """# {name}: brief

Fill this in from the refs (you can see them): what you see, then what you will change in the pack.
vedit measured only the colours below; type, shapes and motion are yours to read.

Refs: {refs}

## Palette (k-means over the refs; share of pixels)
{clusters}

Written to pack.yaml: {guessed} (accent = most saturated cluster with Lab chroma >= 20, however small; ivory =
lightest and ink = darkest, only when light/dark enough for text), and the clusters as ref1..ref{n}. Check
them: skin or sky can win.

## Type
- families seen (serif / sans / hand / mono; weights; Arabic face): (replace this line: none seen yet)
- fonts proposed (OFL/free; files go in fonts/ and pack.yaml `fonts:`, stacks in `font:`): (replace this line: none yet)

## Shapes
- boxes, rules, underlines, corners, shadows, strokes: (replace this line: unchanged from base)

## Motion
- how things arrive and leave (eases, speed, stagger), what keeps moving: (replace this line: unchanged from base)

## Per cue type (what changes in types/<type>.html)
- label: (replace this line: unchanged from base)
- chip: (replace this line: unchanged from base)
- kinetic: (replace this line: unchanged from base)
- big-number: (replace this line: unchanged from base)
- chapter: (replace this line: unchanged from base)
- doodle: (replace this line: unchanged from base)
- screen: (replace this line: unchanged from base)
- plug: (replace this line: unchanged from base)

## Questions for the creator
- (replace this line: none yet)
"""


def new(name: str, src: Path, lang: str | None, log: Path | None = None) -> dict:
    """Make `drafts/<name>/` from base + refs; returns what was done (for the report)."""
    from vedit.styleauthor import refs as refsmod

    d = draft_dir(check_name(name))
    if d.exists():
        raise VeditError(f"draft {name!r} exists at {d}", next=f"vedit style try {name}", exit=2)
    tmp = d.with_name(d.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        files, how = refsmod.gather(src, tmp / "refs", log)
        base = packs.BUILTIN / packs.BASE
        for sub in COPY:
            shutil.copytree(base / sub, tmp / sub)
        (tmp / FONTS).mkdir()
        if (base / DOODLE).is_file():
            shutil.copy2(base / DOODLE, tmp / DOODLE)
        clusters = palette.extract(files)
        guessed = palette.guess(clusters)
        text = (base / "pack.yaml").read_text(encoding="utf-8")
        text = recolor(text, packs.read_yaml(base).get("colors") or {}, guessed)
        head = f"# {name}: draft from {src} ({dt.date.today()}). Edit tokens here, templates in types/.\n"
        text = head + re.sub(r"\A(#.*\n)+", "", text)
        colors = {**(packs.read_yaml(base).get("colors") or {}), **guessed}
        colors.update({f"ref{i + 1}": c.hex for i, c in enumerate(clusters)})
        text = set_key(text, "name", name)
        text = set_key(text, "extends", packs.BASE, after="name")
        text = set_key(text, "summary", f"draft from {Path(src).name}")
        text = set_key(text, "keywords", [name])
        text = set_key(text, "lang", [lang] if lang else ["ar", "en"])
        text = set_key(text, "colors", colors)
        write_yaml(tmp, text)
        (tmp / "palette.json").write_text(
            json.dumps({"clusters": [c.to_dict() for c in clusters], "guess": guessed}, indent=1) + "\n"
        )
        rows = "\n".join(f"- {c.hex}  {c.weight:.0%}" for c in clusters) or "- (no pixels read)"
        (tmp / "brief.md").write_text(
            BRIEF.format(
                name=name,
                refs=", ".join(f"refs/{f.name}" for f in files),
                clusters=rows,
                guessed=", ".join(f"{k} {v}" for k, v in guessed.items()) or "nothing",
                n=len(clusters),
            ),
            encoding="utf-8",
        )
        (tmp / "history.md").write_text(f"# {name}: history\n\n- {dt.date.today()}: draft made; {how}\n")
        tmp.rename(d)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"path": str(d), "refs": [str(d / "refs" / f.name) for f in files], "how": how, "guess": guessed}


def clusters_of(pack_dir: Path) -> list[palette.Cluster]:
    """The refs' clusters: palette.json when present, else extracted from refs/ now (none without refs)."""
    f = pack_dir / "palette.json"
    if f.is_file():
        try:
            rows = json.loads(f.read_text())["clusters"]
            return [palette.Cluster(r["hex"], r["weight"], tuple(r["lab"])) for r in rows]
        except (ValueError, KeyError, TypeError):
            pass
    refs = sorted((pack_dir / "refs").glob("*")) if (pack_dir / "refs").is_dir() else []
    return palette.extract([r for r in refs if r.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}])


# ---- fork / pick / save ----


def _rename(d: Path, new_name: str) -> None:
    write_yaml(d, set_key((d / "pack.yaml").read_text(encoding="utf-8"), "name", new_name))


def log(d: Path, line: str) -> None:
    f = d / "history.md"
    old = f.read_text(encoding="utf-8") if f.is_file() else f"# {d.name.split(SEP)[0]}: history\n\n"
    f.write_text(old.rstrip("\n") + "\n" + line.rstrip("\n") + "\n", encoding="utf-8")


def fork(name: str, variant: str) -> Path:
    src = draft_dir(check_name(name))
    if not (src / "pack.yaml").is_file():
        raise VeditError(f"no draft {name!r} in {drafts_root()}", next=f"vedit style new {name} --from <dir>")
    check_name(variant, "variant")
    if variant == MAIN:
        raise VeditError(f"variant {MAIN!r} means the draft itself; pick another word", exit=2)
    dst = draft_dir(option(name, variant))
    if dst.exists():
        raise VeditError(f"option {dst.name!r} exists at {dst}", next=f"vedit style try {dst.name}", exit=2)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("specimen"))
    _rename(dst, dst.name)
    log(dst, f"- {dt.date.today()}: forked from {name} as option {variant!r}")
    return dst


def archive(d: Path, tag: str) -> Path:
    dst = archive_root() / f"{d.name}-{tag}-{dt.datetime.now():%Y%m%d-%H%M%S}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(d), str(dst))
    return dst


def pick(name: str, variant: str, why: str) -> dict:
    """Keep option `variant` as the draft `name`; archive every other option; log the decision."""
    if variant != MAIN:
        check_name(variant, "variant")
    have = options(check_name(name))
    want = option(name, variant)
    if want not in have:
        raise VeditError(
            f"no option {want!r} (have: {', '.join(have) or 'none'})", next=f"vedit style compare {name}"
        )
    if not why.strip():
        raise VeditError("pick needs the creator's reason: --why '...'", exit=2)
    others = [o for o in have if o != want]
    stamp = f"{dt.date.today()}"
    winner = draft_dir(want)
    archived = {}
    for o in others:  # the draft's own folder too, when a fork wins: the winner takes its name
        archived[o] = str(archive(draft_dir(o), "not-picked"))
    if want != name:
        winner.rename(draft_dir(name))
        winner = draft_dir(name)
        _rename(winner, name)
        shutil.rmtree(winner / "specimen", ignore_errors=True)  # its specimen was rendered as `want`
    over = ", ".join(o.split(SEP)[1] if SEP in o else MAIN for o in others) or "nothing (only option)"
    log(winner, f"\n## {stamp}: picked {variant!r}\n- over: {over}\n- why (the creator): {why.strip()}")
    return {"kept": str(winner), "picked": variant, "over": others, "archived": archived}


def save(name: str, pk: packs.Pack, dest_root: Path, keywords: list[str], replace: bool) -> dict:
    """Move the checked draft to `dest_root/<name>/` with its keywords; the old pack there is archived."""
    src = draft_dir(check_name(name))
    forks = [o for o in options(name) if o != name]
    if forks:
        raise VeditError(
            f"{name!r} still has options ({', '.join(forks)}); the creator picks one first",
            next=f"vedit style compare {name}   then: vedit style pick {name} <variant> --why '...'",
        )
    probs = packs.check(pk)
    if probs:
        raise VeditError(
            f"draft {name!r} has {len(probs)} problem(s), not saved:\n  " + "\n  ".join(probs),
            next=f"fix the draft, then: vedit style try {name}",
        )
    dst = dest_root / name
    replaced = None
    if dst.exists():
        if not replace:
            raise VeditError(
                f"{dst} exists; saving replaces it (the old one is archived)",
                next="add --yes to replace it",
                exit=2,
            )
        replaced = str(archive(dst, "replaced"))
    text = (src / "pack.yaml").read_text(encoding="utf-8")
    if keywords:
        text = set_key(text, "keywords", keywords)
    write_yaml(src, text)
    log(src, f"- {dt.date.today()}: saved to {dst}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return {"path": str(dst), "replaced": replaced}
