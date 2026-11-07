"""Outputs of a project (`project.yaml` `outputs:`): resolving a clip's word range and writing the list back.

The block is rewritten as text so every other line of project.yaml (and its comments) stays as written.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from vedit.graphics.anchors import first_after
from vedit.project import Output, Project, ProjectError, parse_outputs
from vedit.report import VeditError
from vedit.words import model as wm

CLIP_MAX = 600.0  # seconds after `from` that `to` is searched


@dataclass
class Range:
    clip: str
    t0: float  # source time of the first word of `from`
    t1: float  # source time of the end of the last word of `to`
    text_from: str
    text_to: str

    def as_dict(self) -> dict:
        return {"clip": self.clip, "t0": round(self.t0, 3), "t1": round(self.t1, 3),
                "from": self.text_from, "to": self.text_to}  # fmt: skip


def words_by_clip(project: Project) -> dict[str, list[dict]]:
    out = {}
    for clip in project.sources:
        try:
            out[clip] = wm.load(project.paths, clip)
        except VeditError:
            continue
    if not out:
        raise VeditError("no transcript yet: a clip range is found in the words", next="vedit transcribe",
                         code="not_built")  # fmt: skip
    return out


def resolve_range(project: Project, out: Output, wbc: dict[str, list[dict]] | None = None) -> Range:
    """Source-time span of a clip output: `from` found near `near` (or anywhere when said once), `to` the first
    time its words are said after that, within CLIP_MAX seconds."""
    if not out.range:
        raise VeditError(f"output {out.id} has no word range", code="bad_input")
    wbc = wbc if wbc is not None else words_by_clip(project)
    rng = out.range
    near = rng.get("near")
    if near:
        start = wm.find(wbc, rng["from"], near)
    else:
        hits = [wm.find(wbc, rng["from"], f"{c} 0", window=1e9) for c in wbc if _said(wbc[c], rng["from"])]
        if not hits:
            raise VeditError(f"output {out.id}: {rng['from']!r} is not in the transcript", code="bad_input",
                             next="check the words (vedit summarize shows the transcript) or add near: A <s>")  # fmt: skip
        start = hits[0]
    words = wbc[start.clip]
    end = first_after(words, rng["to"], start.clip, start.t0, start.t0 + CLIP_MAX)
    if end is None:
        raise VeditError(
            f"output {out.id}: {rng['to']!r} is not said within {CLIP_MAX:g}s after {rng['from']!r} "
            f"({start.clip} {start.t0:.1f})",
            next="fix `to` (words spoken after `from`)",
            code="bad_input",
        )
    return Range(start.clip, start.t0, end.t1, start.text, end.text)


def _said(words: list[dict], phrase: str) -> bool:
    from vedit.graphics.anchors import spans

    return bool(spans(words, phrase, ""))


_BLOCK = re.compile(r"(?ms)^outputs:\s*\n(?:^[ \t-].*\n?|^\s*\n)*")


def write(project_yaml: Path, outputs: list[Output] | None) -> None:
    """Replace (or remove, with None) the top-level `outputs:` block; everything else is kept byte for byte."""
    text = project_yaml.read_text(encoding="utf-8")
    text = _BLOCK.sub("", text)
    if outputs:
        parse_outputs([o.as_dict() for o in outputs], project_yaml)  # never write a list that won't load
        if text and not text.endswith("\n"):
            text += "\n"
        block = yaml.safe_dump(
            {"outputs": [o.as_dict() for o in outputs]}, sort_keys=False, allow_unicode=True
        )
        text += block
    project_yaml.write_text(text, encoding="utf-8")


def explicit(project_yaml: Path) -> bool:
    try:
        data = yaml.safe_load(project_yaml.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as e:
        raise ProjectError(f"{project_yaml}: {e}") from e
    return "outputs" in data
