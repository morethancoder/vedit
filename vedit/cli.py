"""Command line entry point: stdlib argparse subcommands over a command table."""

import argparse
import importlib
import json
import sys

from vedit import __version__
from vedit.report import VeditError, color_ok

# verb -> (phase, one-line help, module or None while unbuilt).
# A command module exposes `run(ns) -> Report` and optionally `add_args(parser)`; it is imported lazily.
COMMANDS: dict[str, tuple[int, str, str | None]] = {
    "new": (2, "create a project folder for a video or recording", "vedit.commands.new"),
    "importers": (12, "list importer plugins (recorder projects -> sources)", "vedit.commands.importers"),
    "transcribe": (2, "transcribe the source via Studio (cached)", "vedit.commands.transcribe"),
    "summarize": (7, "summary.md: chapters, visual moments, ASR errors", "vedit.commands.summarize"),
    "llm": (7, "run a saved prompt through the model router (JSON out)", "vedit.commands.llm"),
    "propose-cuts": (7, "draft cuts.proposed.yaml for review", "vedit.commands.propose_cuts"),
    "cut": (3, "listen for exact boundaries, render changed pieces", "vedit.commands.cut"),
    "joins": (3, "print only the joins that read wrong", "vedit.commands.joins"),
    "listen": (3, "check audio around a time range", "vedit.commands.listen"),
    "faces": (4, "face track for placement (cached); --sheet draws a check sheet", "vedit.commands.faces"),
    "build": (4, "cues + style pack into a HyperFrames project, checked", "vedit.commands.build"),
    "review": (8, "snapshot sheet at every graphic's peak + flags", "vedit.commands.review"),
    "draft": (8, "1080p draft, opened in QuickTime", "vedit.commands.draft"),
    "subs": (8, "write ar/en SRT", "vedit.commands.subs"),
    "render": (8, "4K60 master, chunked, resumable, detached", "vedit.commands.render"),
    "clean": (8, "remove caches (--posted also deletes originals)", "vedit.commands.clean"),
    "status": (1, "stage, stale outputs, running render progress", "vedit.commands.status"),
    "doctor": (1, "check required tools and environment", "vedit.commands.doctor"),
    "guide": (1, "built-in manual, one page per topic", "vedit.commands.guide"),
    "skill": (1, "print or install the agent skill", "vedit.commands.skill"),
    "styles": (5, "list, find|show style packs (channel, global, built-in)", "vedit.commands.styles"),
    "channel": (5, "add|show a channel's defaults (style, lang, accent, logos)", "vedit.commands.channel"),
    "style": (5, "new|try|fork|compare|pick|save a style", "vedit.commands.style"),
    "doodle": (5, "list doodle scenes; preview one as a draft clip", "vedit.commands.doodle"),
    "commands": (10, "every command and flag as data (--json)", "vedit.commands.commands"),
    "formats": (11, "aspects and platforms: canvas, HUD safe box, crops", "vedit.commands.formats"),
    "output": (11, "list|add|rm outputs: master, clips, shorts, stories, posts", "vedit.commands.output"),
    "reframe": (11, "face-following crop for 9:16, 4:5, 1:1 outputs; --sheet", "vedit.commands.reframe"),
    "wait": (10, "block until the running job ends (--timeout, --events)", "vedit.commands.wait"),
}

# What a command does to the world: reads, writes (project files), renders (video/frames), model (LLM call),
# long (minutes or more; may detach), destructive (deletes). `vedit commands --json` prints these.
EFFECTS: dict[str, list[str]] = {
    "new": ["writes", "renders", "long"],
    "transcribe": ["writes", "long"],
    "summarize": ["writes", "model"],
    "llm": ["reads", "model"],
    "propose-cuts": ["writes", "model"],
    "cut": ["writes", "renders", "long"],
    "joins": ["reads", "long"],
    "listen": ["reads"],
    "faces": ["writes"],
    "build": ["writes"],
    "review": ["writes", "renders"],
    "draft": ["writes", "renders", "long"],
    "subs": ["writes", "model"],
    "render": ["writes", "renders", "long"],
    "clean": ["destructive"],
    "status": ["reads"],
    "doctor": ["reads"],
    "guide": ["reads"],
    "skill": ["reads", "writes"],
    "styles": ["reads"],
    "channel": ["reads", "writes"],
    "style": ["writes", "renders", "model"],
    "doodle": ["reads", "renders"],
    "commands": ["reads"],
    "wait": ["reads"],
    "formats": ["reads"],
    "importers": ["reads"],
    "output": ["reads", "writes"],
    "reframe": ["writes"],
}

# Commands that honour --dry-run (report the plan, write nothing). Others reject it.
DRY_RUN: set[str] = {"clean", "render", "draft", "new", "cut", "build", "subs"}

# verb -> guide topic named in its --help ("" = the overview, plain `vedit guide`).
GUIDE_TOPIC: dict[str, str] = {
    "new": "ingest",
    "transcribe": "ingest",
    "summarize": "drafts",
    "propose-cuts": "drafts",
    "llm": "drafts",
    "cut": "cuts",
    "joins": "cuts",
    "listen": "cuts",
    "faces": "cues",
    "build": "cues",
    "review": "review",
    "draft": "review",
    "subs": "render",
    "render": "render",
    "clean": "render",
    "status": "render",
    "doctor": "errors",
    "guide": "",
    "skill": "",
    "styles": "styles",
    "channel": "channels",
    "style": "style-authoring",
    "doodle": "cue-doodle",
    "commands": "agents",
    "wait": "agents",
    "formats": "formats",
    "importers": "importers",
    "output": "formats",
    "reframe": "formats",
}

# The edit loop in order; "write X" marks a file the agent writes. `vedit guide` renders it from COMMANDS.
LOOP = [
    "new",
    "transcribe",
    "summarize",
    "write cuts.yaml",
    "cut",
    "joins",
    "write cues.yaml",
    "build",
    "review",
    "draft",
    "subs",
    "render",
    "status",
    "clean",
]

# Flags of commands that are not built yet, only those the README/plan names. Keeps guide pages honest:
# tests/test_guide.py accepts these for unbuilt verbs. Remove an entry when its command gets a real parser.
PLANNED_FLAGS: dict[str, list[str]] = {}

# One example line in --help for commands that have no parser of their own yet (from the README loop).
EXAMPLES: dict[str, str] = {
    "summarize": "vedit summarize",
    "propose-cuts": "vedit propose-cuts",
}

EXIT_OK, EXIT_FAILED, EXIT_USAGE = 0, 1, 2


def _globals(p: argparse.ArgumentParser, default, dry: bool = True) -> None:
    """Global flags; accepted before or after the verb (subparsers use SUPPRESS so they don't reset them)."""
    p.add_argument("--json", action="store_true", default=default(False), help="one JSON value on stdout")
    p.add_argument(
        "--project", metavar="PATH", default=default(None), help="project folder (default: walk up)"
    )
    p.add_argument("--yes", action="store_true", default=default(False), help="answer yes to confirmations")
    p.add_argument(
        "--dry-run",
        action="store_true",
        default=default(False),
        help="report what would be done (and its cost) without doing it" if dry else argparse.SUPPRESS,
    )


_JSON_MODE = False


class VeditParser(argparse.ArgumentParser):
    """Usage errors exit 2, as one JSON value when --json is anywhere in argv."""

    def error(self, message):
        if _JSON_MODE:
            print(json.dumps(VeditError(message, next="vedit guide errors", code="usage").to_dict()))
            raise SystemExit(EXIT_USAGE)
        super().error(message)


def _module(verb: str):
    name = COMMANDS[verb][2]
    return importlib.import_module(name) if name else None


DESCRIPTION = (
    "Agent-first CLI that edits a recording of someone speaking (talk, tutorial, podcast, vlog) into a "
    "finished video and short-form clips: cut, word-anchored graphics, subtitles, render. "
    "Not for videos with no recorded speech (ads, music videos, motion graphics). Fit check: vedit guide."
)


def build_parser() -> argparse.ArgumentParser:
    p = VeditParser(prog="vedit", description=DESCRIPTION)
    p.add_argument("--version", action="version", version=f"vedit {__version__}")
    _globals(p, lambda v: v)
    sub = p.add_subparsers(dest="command", metavar="<command>")
    for verb, (phase, text, module) in COMMANDS.items():
        suffix = "" if module else f" [not built yet, phase {phase:02d}]"
        sp = sub.add_parser(
            verb,
            help=text + suffix,
            description=text + suffix,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        _globals(sp, lambda v: argparse.SUPPRESS, dry=verb in DRY_RUN)
        mod = _module(verb) if module else None
        if mod is not None and hasattr(mod, "add_args"):
            mod.add_args(sp)
        elif mod is None:
            sp.add_argument("args", nargs=argparse.REMAINDER, help=argparse.SUPPRESS)
        topic = GUIDE_TOPIC.get(verb, "")
        if not sp.epilog and verb in EXAMPLES:
            sp.epilog = f"example: {EXAMPLES[verb]}"
        tail = f"guide: vedit guide {topic}".rstrip()
        sp.epilog = f"{sp.epilog}\n{tail}" if sp.epilog else tail
    return p


def main(argv: list[str] | None = None) -> int:
    global _JSON_MODE
    _JSON_MODE = "--json" in (sys.argv[1:] if argv is None else argv)
    parser = build_parser()
    ns, extra = parser.parse_known_args(argv)
    if extra and (ns.command is None or COMMANDS[ns.command][2]):
        parser.error(f"unrecognized arguments: {' '.join(extra)}")
    if ns.command is None:
        parser.print_help()
        return EXIT_USAGE
    phase, _, module = COMMANDS[ns.command]
    if module is None:
        msg = f"vedit {ns.command}: not built yet (phase {phase:02d})"
        topic = GUIDE_TOPIC.get(ns.command, "")
        nxt = f"vedit guide {topic}".rstrip()
        if ns.json:
            print(json.dumps(VeditError(msg, next=nxt, code="usage").to_dict()))
        else:
            print(msg, file=sys.stderr)
            print(f"next: {nxt}", file=sys.stderr)
        return EXIT_USAGE
    if ns.dry_run and ns.command not in DRY_RUN:
        e = VeditError(
            f"vedit {ns.command} has no --dry-run (it has: {', '.join(sorted(DRY_RUN))})",
            next=f"vedit {ns.command} --help",
            code="usage",
        )
        if ns.json:
            print(json.dumps(e.to_dict()))
        else:
            print(f"error: {e.message}  [usage]", file=sys.stderr)
        return EXIT_USAGE
    try:
        report = _module(ns.command).run(ns)
    except VeditError as e:
        if ns.json:
            print(json.dumps(e.to_dict(), ensure_ascii=False))
        else:
            print(f"error: {e.message}  [{e.code}]", file=sys.stderr)
            if e.next:
                print(f"next: {e.next}", file=sys.stderr)
        return e.exit
    if ns.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False))
    else:
        text = report.to_text(color_ok())
        if text:
            print(text)
    return EXIT_OK if report.ok else EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main())
