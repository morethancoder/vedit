"""vedit llm <prompt>: run one saved prompt through the model router and print its validated JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from vedit import llm
from vedit.project import Project, ProjectError, find_project
from vedit.report import Report, VeditError, color_ok

EPILOG = "example: vedit llm summary --model sonnet > summary.json"


def add_args(sp) -> None:
    sp.add_argument("prompt", nargs="?", help="prompt name; omit to list them")
    sp.add_argument("--input", metavar="FILE", help="text to run on (default: transcript)")
    sp.add_argument("--notes", metavar="FILE", help="speaker's outline, as context")
    names = ["auto", *llm.MODELS]
    sp.add_argument("--model", default="auto", choices=names, metavar="M", help=f"{'|'.join(names)} (auto)")
    sp.epilog = EPILOG


def find(ns) -> Project | None:
    try:
        return Project.load(find_project(override=ns.project))
    except ProjectError as e:
        if ns.project:
            raise VeditError(str(e), next="vedit llm <prompt> --input FILE") from e
        return None


def run(ns) -> Report:
    r = Report("llm")
    if not ns.prompt:
        for name in llm.prompt_names():
            p = llm.load_prompt(name)
            r.info(f"{name:10} {p.model:7} batch {p.batch or 'all'}")
        r.data = {"prompts": {n: llm.load_prompt(n).model for n in llm.prompt_names()}}
        r.next = "vedit llm <prompt>"
        return r
    prompt = llm.load_prompt(ns.prompt)
    project = find(ns)
    notes = Path(ns.notes).read_text(encoding="utf-8") if ns.notes else None
    if ns.input:
        text = Path(ns.input).read_text(encoding="utf-8")
    elif project:
        text = llm.transcript(project)
    else:
        raise VeditError("no --input and no project here", next="vedit llm <prompt> --input FILE")
    ctx = llm.context(project, notes) if project else (notes or "")
    log = project.paths.logs / "llm.jsonl" if project else None
    res = llm.ask(prompt, text, vars={"context": ctx}, model=ns.model, log=log)
    value = res.values[0] if len(res.values) == 1 else res.values
    r.data = {"result": value, **usage(res)}
    report_usage(r, res)
    r.next = "vedit guide drafts"
    if ns.json:
        return r
    # stdout carries only the JSON so it can be piped; the short report goes to stderr.
    print(json.dumps(value, ensure_ascii=False, indent=1))
    print(r.to_text(color_ok(sys.stderr)), file=sys.stderr)
    return Report("llm")


def usage(res: llm.Result) -> dict:
    return {
        "models": res.models,
        "tokens_in": res.tokens_in,
        "tokens_out": res.tokens_out,
        "cost_usd": round(res.cost_usd, 4),
        "seconds": round(res.seconds, 1),
        "fallbacks": res.fallbacks,
        "retries": res.retries,
    }


def report_usage(r: Report, res: llm.Result) -> None:
    models = ", ".join(sorted(set(res.models)))
    r.info(
        f"{models}: {res.tokens_in} in / {res.tokens_out} out tokens, "
        f"${res.cost_usd:.3f} list price, {res.seconds:.0f}s"
    )
    for f in res.fallbacks:
        r.warn(f"fell back after {f}")
    for f in res.retries:
        r.info(f"retried after {f}")
