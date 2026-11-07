"""vedit channel: one YouTube channel's defaults (channel.yaml), its own style packs and plug preset.

    vedit channel add <handle> [--style S --lang ar|en --dialect D --accent #HEX --logos a,b --hint TEXT]
    vedit channel show [<handle>]

Files under `<config_dir>/channels/<handle>/`: channel.yaml, styles/<name>/ (channel-only packs),
plug/plug.yaml (+ files). `add` on an existing handle changes only the flags given.
"""

from __future__ import annotations

import argparse
import re

from vedit import channel as chan
from vedit.commands.new import project_langs
from vedit.graphics import pack as packs
from vedit.report import Report, VeditError

EPILOG = "example: vedit channel add ali-talks --style yellow-doodle --lang ar --accent '#FFD60A'"
HANDLE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
HEX = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")


def add_args(sp) -> None:
    sp.usage = "vedit channel {add,show} [handle] [--style NAME] [--lang ar|en] [--accent #HEX] [...]"
    sp.add_argument("action", choices=["add", "show"], help=argparse.SUPPRESS)
    sp.add_argument("handle", nargs="?", help=argparse.SUPPRESS)
    sp.add_argument("--style", metavar="NAME", help="default style pack (must resolve for this channel)")
    sp.add_argument("--lang", choices=project_langs(), metavar="ar|en", help="spoken language")
    sp.add_argument("--dialect", metavar="D", help="ar dialect: iq, gulf, lev, eg, ma, msa")
    sp.add_argument("--accent", metavar="#HEX", help="accent colour that replaces the style's accent")
    sp.add_argument("--logos", metavar="A,B", help="logo names the channel uses, comma separated")
    sp.add_argument("--hint", metavar="TEXT", help="transcription hint (names, jargon)")
    sp.epilog = EPILOG


def describe(handle: str) -> dict:
    d = chan.channel_file(handle).parent
    data = chan.load_channel(handle) or {}
    plug = d / "plug" / "plug.yaml"
    own = [n for n, _, _ in packs.available([packs.channel_root(handle)])]
    return {
        "handle": handle,
        "path": str(d),
        "default": chan.default_channel() == handle,
        "channel": data,
        "styles": own,
        "plug": str(plug) if plug.is_file() else None,
    }


def add(ns) -> Report:
    h = ns.handle
    if not h or not HANDLE.match(h):
        raise VeditError(
            f"channel handle {h!r} must be letters, digits, . _ - (e.g. ali-talks)",
            next="vedit channel add <handle> --style <name> --lang ar",
            exit=2,
        )
    if ns.accent and not HEX.match(ns.accent):
        raise VeditError(f"--accent {ns.accent!r} must be a hex colour like #FFD60A", exit=2)
    if ns.style:
        packs.load(ns.style, packs.pack_roots(h))  # not found: the error names the places searched
    data = dict(chan.load_channel(h) or {})
    given = {
        "style": ns.style,
        "lang": ns.lang,
        "dialect": ns.dialect,
        "accent": ns.accent,
        "hint": ns.hint,
        "logos": [x.strip() for x in ns.logos.split(",") if x.strip()] if ns.logos else None,
    }
    existed = chan.channel_file(h).is_file()
    data.update({k: v for k, v in given.items() if v})
    f = chan.save_channel(h, data)
    r = Report("channel")
    r.step(f"{h}  ({f.parent})")
    r.ok_(("updated " if existed else "created ") + str(f))
    r.info(", ".join(f"{k} {v}" for k, v in data.items()) or "no defaults yet")
    r.data = describe(h)
    if not data.get("style"):
        r.warn("no default style: projects fall back to the global default or base")
    r.next = f"vedit new <input> --channel {h}  (or: vedit channel show {h})"
    return r


def show(ns) -> Report:
    h = ns.handle or chan.default_channel()
    if not h:
        names = chan.channels()
        r = Report("channel")
        r.step("channels")
        for n in names:
            r.info(f"{n}  {chan.load_channel(n) or {}}")
        if not names:
            r.warn("no channels yet")
        r.data = {"channels": [describe(n) for n in names]}
        r.next = "vedit channel add <handle> --style <name> --lang ar"
        return r
    if not chan.channel_file(h).is_file():
        have = chan.channels()
        raise VeditError(
            f"channel {h!r} not found in {chan.config_dir() / 'channels'} (have: {', '.join(have) or 'none'})",
            next=f"vedit channel add {h} --style <name> --lang ar",
        )
    d = describe(h)
    r = Report("channel")
    r.step(f"{h}  ({d['path']})" + ("  [default channel]" if d["default"] else ""))
    for k in chan.CHANNEL_KEYS:
        r.info(f"{k}: {d['channel'].get(k, '-')}")
    r.info(f"own styles: {', '.join(d['styles']) or 'none'}  (resolve before global and built-in)")
    r.info(f"plug preset: {d['plug'] or 'none (project custom/plug/ or brand text)'}")
    r.data = d
    r.next = "vedit styles --channel " + h
    return r


def run(ns) -> Report:
    return add(ns) if ns.action == "add" else show(ns)
