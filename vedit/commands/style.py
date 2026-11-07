"""vedit style: author a style pack from reference images, by try and judge.

    vedit style new <name> --from <dir|image|video> [--lang ar|en]   draft from base + refs + palette + brief.md
    vedit style try <name> [--clip] [--force]                         specimen sheet (+ ~10 s draft clip)
    vedit style fork <name> <variant>                                 an option: drafts/<name>@<variant>/
    vedit style compare <a> <b> ... [--no-open]                       one sheet side by side; clips in QuickTime
    vedit style pick <name> <variant> --why "..."                     the creator's choice kept as <name>, logged
    vedit style save <name> --global --keywords "..." | --channel H   checked, promoted out of drafts/

Names resolve drafts > channel > global > built-in, so built-in packs can be tried and compared too.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from vedit.commands.styles import channel_of
from vedit.graphics import pack as packs
from vedit.report import Report, VeditError
from vedit.run import run as sh
from vedit.styleauthor import drafts, palette, sheet, specimen

ACTIONS = ("new", "try", "fork", "compare", "pick", "save")
EPILOG = "example: vedit style new warm-hand --from ~/refs/warm   then: vedit style try warm-hand --clip"


def add_args(sp) -> None:
    sp.usage = "vedit style {new,try,fork,compare,pick,save} NAME [VARIANT|NAME...] [flags]"
    sp.description = None  # the usage line says it; keeps --help short
    sp.add_argument("action", choices=ACTIONS, help=argparse.SUPPRESS)
    sp.add_argument("names", nargs="*", help=argparse.SUPPRESS)
    sp.add_argument(
        "--from", dest="src", metavar="PATH", help="new: folder of screenshots, an image or a video"
    )
    sp.add_argument(
        "--lang", choices=["ar", "en"], help="new: the language the pack is drawn for (specimen text)"
    )
    sp.add_argument("--clip", action="store_true", help="try: also render a ~12 s 1080p draft clip (motion)")
    sp.add_argument("--force", action="store_true", help="try/compare: render again even if nothing changed")
    sp.add_argument("--no-open", action="store_true", help="compare: do not open the clips in QuickTime")
    sp.add_argument("--why", metavar="TEXT", default="", help="pick: The creator's reason, logged in history.md")
    sp.add_argument("--global", dest="glob", action="store_true", help="save: into the global styles")
    sp.add_argument(
        "--channel", metavar="HANDLE", help="save: into this channel's styles (also resolves names)"
    )
    sp.add_argument(
        "--keywords", metavar="WORDS", default="", help="save: words for `styles find` (comma/space)"
    )
    sp.epilog = EPILOG


def _log() -> Path:
    return drafts.cache_root() / "logs" / "style.log"


def _need(ns, n: int, usage: str) -> list[str]:
    if len(ns.names) != n:
        raise VeditError(f"usage: vedit style {usage}", next="vedit guide style-authoring", exit=2)
    return ns.names


def _load(name: str, ns) -> packs.Pack:
    return packs.load(name, drafts.roots(channel_of(ns)))


# ---- new ----


def new(ns) -> Report:
    (name,) = _need(ns, 1, "new <name> --from <dir|image|video> [--lang ar|en]")
    if not ns.src:
        raise VeditError("vedit style new needs --from <folder of screenshots | video>", exit=2)
    res = drafts.new(name, Path(ns.src), ns.lang, _log())
    r = Report("style")
    r.ok_(f"draft {name}: {res['path']}")
    r.info(res["how"])
    r.info("palette guess: " + (", ".join(f"{k} {v}" for k, v in res["guess"].items()) or "none"))
    r.info("edit: brief.md (what you see), pack.yaml (tokens, fonts), types/*.html (shapes, motion)")
    r.data = res
    r.next = f"look at refs/, fill brief.md, edit the pack, then: vedit style try {name}"
    return r


# ---- try ----


def tiles_of(name: str, ns, log: Path) -> tuple[packs.Pack, dict, specimen.Built]:
    pk = _load(name, ns)
    probs = packs.check(pk)
    if probs:
        raise VeditError(
            f"style {name!r} has {len(probs)} problem(s), nothing rendered:\n  " + "\n  ".join(probs),
            next=f"fix them, then: vedit style try {name}",
        )
    have, b, _ = specimen.sheet_tiles(pk, ns.force, log)
    return pk, have, b


def tile_rows(b: specimen.Built, have: dict, spec_ids: list[str]) -> list[tuple[str, Path | None, str]]:
    return [(tid, have.get(tid), b.problems.get(tid, "")) for tid in spec_ids]


def run_try(ns) -> Report:
    (name,) = _need(ns, 1, "try <name> [--clip]")
    log = _log()
    pk, have, b = tiles_of(name, ns, log)
    ids = [t["id"] for t in specimen.load_spec()["tiles"]]
    folder = pk.dirs[0]
    clusters = drafts.clusters_of(folder)
    dist = palette.distance(pk.data.get("colors") or {}, clusters)
    refs = sorted((folder / "refs").glob("*")) if (folder / "refs").is_dir() else []
    out = specimen.out_dir(pk)
    title = f"{name}  ({specimen.lang_of(pk)})" + (f"   palette dE {dist['mean']}" if dist else "")
    png = sheet.specimen(
        title,
        tile_rows(b, have, ids),
        refs,
        list(palette.pack_colors(pk.data.get("colors") or {}).items()),
        [(f"{c.weight:.0%}", c.hex) for c in clusters],
        out / "specimen.png",
    )
    r = Report("style")
    r.ok_(f"specimen: {png}  ({len(have)} of {len(ids)} tiles)")
    for tid, why in b.problems.items():
        r.warn(f"{tid}: not rendered: {why}")
    mp4 = None
    if ns.clip:
        mp4, _ = specimen.clip(pk, ns.force, log)
        r.ok_(f"clip: {mp4}")
    if dist:
        r.info(
            f"palette distance to refs: mean dE {dist['mean']} (CIE76; <3 same, ~10 near, >25 another colour)"
        )
        for k, v in dist["per"].items():
            r.info(f"  {k} {v['hex']} -> {v['nearest']}  dE {v['de']}")
    else:
        r.info("palette distance: no refs for this pack")
    r.data = {
        "name": name,
        "path": str(folder),
        "specimen": str(png),
        "clip": str(mp4) if mp4 else None,
        "tiles": {k: str(v) for k, v in have.items()},
        "problems": b.problems,
        "palette": dist,
        "log": str(log),
    }
    is_draft = folder.parent == drafts.drafts_root()
    r.next = (
        f"look at {png}; edit and try again, or: vedit style fork {name} <variant>"
        if is_draft
        else f"vedit style compare {name} <other>"
    )
    return r


# ---- fork / compare / pick / save ----


def fork(ns) -> Report:
    name, variant = _need(ns, 2, "fork <name> <variant>")
    d = drafts.fork(name, variant)
    r = Report("style")
    r.ok_(f"option {d.name}: {d}")
    r.data = {"name": d.name, "path": str(d), "options": drafts.options(name)}
    r.next = f"edit {d}, then: vedit style try {d.name}   and: vedit style compare {name}"
    return r


def compare(ns) -> Report:
    names = list(ns.names)
    if len(names) == 1:
        names = drafts.options(names[0]) or names
    if len(names) < 2:
        raise VeditError("compare needs two or more styles (or a draft with forks)", exit=2)
    log = _log()
    ids = [t["id"] for t in specimen.load_spec()["tiles"]]
    cols, clips, data = [], [], {}
    for n in names:
        pk, have, b = tiles_of(n, ns, log)
        dist = palette.distance(pk.data.get("colors") or {}, drafts.clusters_of(pk.dirs[0]))
        label = n + (f"  dE {dist['mean']}" if dist else "")
        cols.append((label, {t: (have.get(t), b.problems.get(t, "")) for t in ids}))
        clip = specimen.out_dir(pk) / "specimen.mp4"
        if not ns.no_open and (ns.force or not clip.is_file()):
            clip, _ = specimen.clip(pk, ns.force, log)
        if clip.is_file():
            clips.append(clip)
        data[n] = {"specimen_dir": str(specimen.out_dir(pk)), "palette": dist, "clip": str(clip)}
    out = drafts.cache_root() / "compare" / ("+".join(names) + ".png")
    sheet.compare(cols, ids, out)
    r = Report("style")
    r.ok_(f"compare sheet: {out}")
    if clips and not ns.no_open:
        sh(["open", "-a", "QuickTime Player", *map(str, clips)], 60, check=False)
        r.info(f"opened {len(clips)} clips in QuickTime")
    for c in clips:
        r.info(f"clip: {c}")
    r.data = {"sheet": str(out), "styles": data, "opened": not ns.no_open}
    base = names[0].split(drafts.SEP)[0]
    if len(drafts.options(base)) > 1:
        r.next = (
            f"the creator picks: vedit style pick {base} <variant> --why '...'  ({drafts.MAIN} = the draft itself)"
        )
    else:
        r.next = f"look at {out}; set `style: <name>` in project.yaml, or fork a draft: vedit style fork"
    return r


def pick(ns) -> Report:
    name, variant = _need(ns, 2, "pick <name> <variant> --why '...'")
    res = drafts.pick(name, variant, ns.why)
    r = Report("style")
    r.ok_(f"kept {variant!r} as {name}: {res['kept']}")
    for o, where in res["archived"].items():
        r.info(f"archived {o}: {where}")
    r.data = res
    r.next = f"vedit style try {name}, then: vedit style save {name} --global --keywords '...'"
    return r


def save(ns) -> Report:
    (name,) = _need(ns, 1, "save <name> --global --keywords '...' | --channel <handle>")
    if ns.glob == bool(ns.channel):
        raise VeditError("save needs exactly one of --global or --channel <handle>", exit=2)
    drafts.check_name(name)
    if ns.channel:
        channel_of(ns)  # checks the handle
    if not (drafts.draft_dir(name) / "pack.yaml").is_file():
        raise VeditError(
            f"no draft {name!r} in {drafts.drafts_root()}", next="vedit style new <name> --from <dir>"
        )
    dest = packs.user_root() if ns.glob else packs.channel_root(ns.channel)
    pk = packs.load(name, [drafts.drafts_root(), *packs.pack_roots(ns.channel)])
    words = [w for w in ns.keywords.replace(",", " ").split() if w]
    res = drafts.save(name, pk, dest, words, ns.yes)
    r = Report("style")
    r.ok_(f"saved {name} ({'global' if ns.glob else 'channel:' + ns.channel}): {res['path']}")
    if res["replaced"]:
        r.info(f"the pack it replaced is archived at {res['replaced']}")
    r.data = res
    r.next = f"set `style: {name}` in project.yaml (or cues.yaml), then: vedit build"
    return r


def run(ns) -> Report:
    return {"new": new, "try": run_try, "fork": fork, "compare": compare, "pick": pick, "save": save}[
        ns.action
    ](ns)
