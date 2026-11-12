"""vedit skill [install]: print the agent skill, or write a short pointer SKILL.md for Claude."""

from pathlib import Path

from vedit.commands.guide import _dir
from vedit.report import Report, VeditError, confirm

EPILOG = "example: vedit skill install --yes"

POINTER = """---
name: vedit
description: Edit a recording of someone speaking (talk, tutorial, podcast, vlog) into a finished video with the vedit CLI (cuts, graphics, subtitles, render, short-form clips). Use when asked to edit, cut, caption, clip or render a recording. Not for videos with no recorded speech (ads, launch films, music videos, motion graphics, generated explainers).
---
Run `vedit skill` for the full instructions, then `vedit guide` for the map.
Run `vedit guide <topic>` before writing cuts.yaml or cues.yaml.
"""

AGENTS = """## vedit (video editing CLI)
Editing a recording of someone speaking into a video or short-form clips (not for videos with no
recorded speech): run `vedit skill`, then `vedit guide`.
Run `vedit guide <topic>` before writing cuts.yaml or cues.yaml."""


def add_args(sp) -> None:
    sp.add_argument("action", nargs="?", choices=["install"], help="install: write the pointer SKILL.md")
    sp.epilog = EPILOG


def skill_text() -> str:
    return (_dir() / "skill.md").read_text(encoding="utf-8")


def target() -> Path:
    return Path.home() / ".claude" / "skills" / "vedit" / "SKILL.md"


def run(ns) -> Report:
    r = Report("skill")
    if ns.action != "install":
        text = skill_text().strip("\n")
        r.info(text)
        r.data = {"text": text}
        r.next = "vedit guide"
        return r
    path = target()
    differs = path.exists() and path.read_text(encoding="utf-8") != POINTER
    if differs and not confirm(f"{path} exists with different content; overwrite?", ns.yes):
        raise VeditError(f"{path} exists with different content", next="vedit skill install --yes")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(POINTER, encoding="utf-8")
    r.ok_(f"wrote {path} ({len(POINTER.splitlines())} lines, a pointer; the text stays in vedit)")
    r.step("for other agents, add this to AGENTS.md")
    r.info(AGENTS)
    r.data = {"path": str(path), "agents_md": AGENTS}
    r.next = "vedit guide"
    return r
