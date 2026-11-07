"""vedit styles: list style packs (channel, global, built-in), `find` them by words, `show` one's tokens.

    vedit styles [--channel H]                               list: name, scope, summary, types, problems
    vedit styles find "warm doodle arabic" [--channel H]     rank packs by keyword overlap
    vedit styles show <name> [--channel H]                   tokens in a few lines + specimen path

The channel defaults to the project's (when run inside one). A name resolves channel > global > built-in.
"""

from __future__ import annotations

import argparse

from vedit import channel as chan
from vedit.commands.channel import HANDLE
from vedit.graphics import pack as packs
from vedit.graphics import stylefind
from vedit.project import ProjectError, find_project
from vedit.report import Report, VeditError

EPILOG = 'example: vedit styles find "warm doodle arabic"   |   vedit styles show yellow-doodle'


def add_args(sp) -> None:
    sp.add_argument("--channel", metavar="HANDLE", help="include this channel's own packs")
    sp.add_argument("args", nargs="*", metavar="find WORDS | show NAME", help=argparse.SUPPRESS)
    sp.epilog = EPILOG


def scope(root) -> str:
    return packs.scope_of(root)


def channel_of(ns) -> str | None:
    """--channel, else the project's channel when run inside a project."""
    if ns.channel:
        if not HANDLE.match(ns.channel):
            raise VeditError(
                f"--channel {ns.channel!r} must be letters, digits, . _ - (e.g. ali-talks)", exit=2
            )
        return ns.channel
    try:
        return chan.project_channel(find_project(override=ns.project))
    except ProjectError:
        return None


def describe(name: str, folder, root, hidden_by: str | None, roots: list | None = None) -> dict:
    """One pack's row: where it lives, summary, keywords, extends, types by source, problems (never raises)."""
    row = {
        "name": name,
        "scope": scope(root),
        "path": str(folder),
        "summary": "",
        "keywords": [],
        "extends": None,
        "own": [],
        "inherited": {},
        "problems": [],
        "hidden_by": hidden_by,
    }
    try:
        raw = packs.read_yaml(folder)
        row["summary"] = str(raw.get("summary") or "")
        row["keywords"] = [str(k) for k in raw.get("keywords") or []]
        row["extends"] = raw.get("extends") or (packs.BASE if name != packs.BASE else None)
        # a hidden pack is shown as itself: resolve it from its own root first
        pk = packs.load(name, [root, *[r for r in (roots or packs.pack_roots()) if r != root]])
    except VeditError as e:
        row["problems"] = [e.message]
        return row
    src = pk.type_sources()
    row["own"] = [t for t, p in src.items() if p == name]
    row["inherited"] = {t: p for t, p in src.items() if p != name}
    row["problems"] = packs.check(pk)
    return row


def rows_of(roots: list) -> list[dict]:
    seen: dict[str, str] = {}
    rows = []
    for name, folder, root in packs.available(roots):
        rows.append(describe(name, folder, root, seen.get(name), roots))
        seen.setdefault(name, scope(root))
    return rows


def specimen(folder) -> str | None:
    """The pack's specimen sheet (`vedit style try`): in the pack, or the cache for a built-in pack."""
    from vedit.styleauthor.drafts import cache_root

    f = cache_root() / folder.name if folder.parent == packs.BUILTIN else folder / "specimen"
    f = f / "specimen.png"
    return str(f) if f.is_file() else None


def inherited_by(row: dict) -> dict[str, list[str]]:
    by: dict[str, list[str]] = {}
    for t, p in row["inherited"].items():
        by.setdefault(p, []).append(t)
    return by


def find(ns, roots: list) -> Report:
    query = " ".join(ns.args[1:]).strip()
    if not query:
        raise VeditError('vedit styles find needs words, e.g. vedit styles find "warm doodle arabic"', exit=2)
    hits = stylefind.rank(query, [r for r in rows_of(roots) if not r["hidden_by"]])
    r = Report("styles")
    r.step(f"styles matching {query!r}")
    for h in hits[:5]:
        r.info(f"{h['score']:>3}  {h['name']}  ({h['scope']})  matched: {', '.join(h['matched'])}")
        r.info(f"     {h['summary']}")
    if not hits:
        r.warn("no style matches those words")
    keys = ("name", "scope", "score", "matched", "summary")
    r.data = {"query": query, "matches": [{k: h[k] for k in keys} for h in hits[:5]]}
    r.next = (
        f"vedit styles show {hits[0]['name']}"
        if hits
        else "vedit styles  (every pack), or make one: vedit guide style-authoring"
    )
    return r


def show(ns, roots: list) -> Report:
    if len(ns.args) != 2:
        raise VeditError("vedit styles show needs one style name", next="vedit styles", exit=2)
    name = ns.args[1]
    pk = packs.load(name, roots)  # an unknown name is an error naming the places searched
    folder = pk.dirs[0]
    row = describe(name, folder, folder.parent, None, roots)
    colors = dict(pk.data.get("colors") or {})
    fonts = {k: str(v).split(",")[0].strip("\"' ") for k, v in (pk.data.get("font") or {}).items()}
    r = Report("styles")
    r.step(f"{name}  ({row['scope']})  {row['summary']}".rstrip())
    r.info(f"path: {folder}" + (f"  extends {row['extends']}" if row["extends"] else ""))
    r.info("colors: " + (", ".join(f"{k} {v}" for k, v in colors.items()) or "none"))
    r.info("fonts: " + (", ".join(f"{k} {v}" for k, v in fonts.items()) or "none"))
    r.info(
        f"lang: {', '.join(map(str, pk.data.get('lang') or [])) or 'any'}  keywords: {', '.join(row['keywords'])}"
    )
    r.info(f"own types: {', '.join(row['own']) or 'none'}")
    for p, ts in inherited_by(row).items():
        r.info(f"types from {p}: {', '.join(ts)}")
    sp = specimen(folder)
    r.info(f"specimen: {sp}" if sp else f"specimen: none yet; `vedit style try {name}` makes one")
    for x in row["problems"]:
        r.fail(f"{name}: {x}")
    r.data = {**row, "colors": colors, "fonts": fonts, "specimen": sp}
    r.next = f"set `style: {name}` in project.yaml or cues.yaml"
    return r


def run(ns) -> Report:
    handle = channel_of(ns)
    roots = packs.pack_roots(handle)
    if ns.args and ns.args[0] == "find":
        return find(ns, roots)
    if ns.args and ns.args[0] == "show":
        return show(ns, roots)
    if ns.args:
        raise VeditError(
            f"vedit styles: unknown action {ns.args[0]!r} (use: find WORDS, show NAME, or nothing to list)",
            next="vedit guide styles",
            exit=2,
        )
    r = Report("styles")
    rows = rows_of(roots)
    for row in rows:
        head = f"{row['name']}  ({row['scope']}"
        head += f", hidden by the {row['hidden_by']} pack)" if row["hidden_by"] else ")"
        r.step(head + (f"  {row['summary']}" if row["summary"] else ""))
        r.info(f"  {row['path']}" + (f"  extends {row['extends']}" if row["extends"] else ""))
        r.info(f"  own types: {', '.join(row['own']) or 'none'}")
        for p, ts in inherited_by(row).items():
            r.info(f"  from {p}: {', '.join(ts)}")
        for x in row["problems"]:
            r.fail(f"{row['name']}: {x}")
    bad = [row["name"] for row in rows if row["problems"]]
    r.data = {"packs": rows, "roots": [str(x) for x in roots], "channel": handle}
    if bad:
        r.next = f"fix {', '.join(bad)} (vedit guide styles), then: vedit styles"
    else:
        r.next = "vedit styles find WORDS, or set `style: <name>` in project.yaml or cues.yaml"
    return r
