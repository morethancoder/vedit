"""vedit commands: the whole command surface as data (names, flags, guide topics, side effects), so an agent
reads it once instead of scraping every `--help`."""

from __future__ import annotations

import argparse

from vedit.report import Report

EPILOG = "example: vedit commands --json"
GLOBAL = {"json", "project", "yes", "dry_run", "help"}


def add_args(sp) -> None:
    sp.epilog = EPILOG


def _type(a: argparse.Action) -> str:
    if isinstance(a, (argparse._StoreTrueAction, argparse._StoreFalseAction)):
        return "bool"
    if a.nargs in ("*", "+") or isinstance(a, argparse._AppendAction):
        return "list"
    if a.type in (int, float):
        return a.type.__name__
    return "str"


def _flag(a: argparse.Action) -> dict:
    default = a.default if a.default is not argparse.SUPPRESS else None
    if isinstance(default, (set, tuple)):
        default = list(default)
    elif default is not None and not isinstance(default, (str, int, float, bool, list)):
        default = str(default)
    return {
        "name": max(a.option_strings, key=len) if a.option_strings else a.dest,
        "positional": not a.option_strings,
        "type": _type(a),
        "default": default,
        "choices": list(a.choices) if a.choices else None,
        "required": bool(a.required) if a.option_strings else a.nargs not in ("?", "*"),
        "help": a.help if a.help is not argparse.SUPPRESS else None,
    }


def surface() -> list[dict]:
    from vedit import cli

    parser = cli.build_parser()
    sub = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    out = []
    for verb, (_phase, text, module) in cli.COMMANDS.items():
        sp = sub.choices[verb]
        flags = [
            _flag(a)
            for a in sp._actions
            if a.dest not in GLOBAL and (a.help is not argparse.SUPPRESS or not a.option_strings)
        ]
        epi = sp.epilog or ""
        example = next(
            (ln[len("example: ") :] for ln in epi.splitlines() if ln.startswith("example: ")), None
        )
        out.append({
            "name": verb,
            "summary": text,
            "built": module is not None,
            "guide": f"vedit guide {cli.GUIDE_TOPIC.get(verb, '')}".rstrip(),
            "example": example,
            "effects": cli.EFFECTS[verb],
            "dry_run": verb in cli.DRY_RUN,
            "flags": flags,
        })  # fmt: skip
    return out


def run(ns) -> Report:
    from vedit import cli
    from vedit.report import CODES

    r = Report("commands")
    cmds = surface()
    for c in cmds:
        r.info(f"{c['name']:<13} {','.join(c['effects']):<24} {c['summary']}")
    r.data = {
        "commands": cmds,
        "global_flags": ["--json", "--project PATH", "--yes", "--dry-run"],
        "loop": cli.LOOP,
        "error_codes": CODES,
    }
    r.next = "vedit guide"
    return r
