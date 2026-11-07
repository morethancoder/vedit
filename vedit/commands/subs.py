"""vedit subs: subs/ar.srt, en.srt and en.txt from the program transcription, cleaned and translated by a model."""

from __future__ import annotations

import json
import re
from pathlib import Path

from vedit import llm, state
from vedit.commands.llm import report_usage
from vedit.commands.transcribe import _find, _write
from vedit.report import Report, VeditError
from vedit.run import hash_of
from vedit.subs import cues as cuemod
from vedit.subs import srt

EPILOG = "example: vedit subs"
LANGS = {"ar": "Arabic", "en": "English"}
BATCH = 40


def add_args(sp) -> None:
    sp.add_argument(
        "--model", default="auto", choices=["auto", *llm.MODELS], metavar="M", help="force a model"
    )
    sp.add_argument("--force", action="store_true", help="ask the model again even when a result is cached")
    sp.epilog = EPILOG


def checker(want: set[str]):
    def check(value: dict, _text: str) -> None:
        for key in ("src", "tr"):
            got = {str(k) for k in value[key]}
            if got != want:
                missing, extra = sorted(want - got, key=int), sorted(got - want)
                raise llm.Invalid(
                    f"{key}: ids must be exactly the input ids (missing {missing}, extra {extra})"
                )
            for k, v in value[key].items():
                if not isinstance(v, str) or not v.strip():
                    raise llm.Invalid(f"{key}[{k}] is empty or not a string")

    return check


def translate(cues, prompt, vars, model, cache: Path, log: Path, force: bool) -> tuple[dict, dict, dict]:
    """-> (src lines, tr lines, usage) by cue id; each batch of 40 is cached by the hash of what it was asked."""
    src, tr = {}, {}
    use = {"batches": 0, "cached": 0, "models": [], "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0,
           "seconds": 0.0, "fallbacks": [], "retries": []}  # fmt: skip
    cache.mkdir(parents=True, exist_ok=True)
    for i in range(0, len(cues), BATCH):
        chunk = cues[i : i + BATCH]
        text = "\n".join(f"{c['id']}: {c['text']}" for c in chunk) + "\n"
        f = cache / f"{hash_of(prompt.body, prompt.meta, vars, text)}.json"
        use["batches"] += 1
        if not force and f.is_file():
            value = json.loads(f.read_text(encoding="utf-8"))
            use["cached"] += 1
        else:
            res = llm.ask(
                prompt, text, vars=vars, model=model, log=log, check=checker({str(c["id"]) for c in chunk})
            )
            value = res.values[0]
            f.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
            use["models"] += res.models
            use["tokens_in"] += res.tokens_in
            use["tokens_out"] += res.tokens_out
            use["cost_usd"] += res.cost_usd
            use["seconds"] += res.seconds
            use["fallbacks"] += res.fallbacks
            use["retries"] += res.retries
        src.update({int(k): re.sub(r"\s+", " ", v).strip() for k, v in value["src"].items()})
        tr.update({int(k): re.sub(r"\s+", " ", v).strip() for k, v in value["tr"].items()})
    return src, tr, use


def run(ns) -> Report:
    root, project = _find(ns)
    paths = project.paths
    f = paths.program / "P.words.json"
    if not f.is_file():
        raise VeditError("no program transcription yet: the cut has not been made", next="vedit cut")
    lang = project.lang
    if lang not in LANGS:
        raise VeditError(
            f"subs writes Arabic and English; the project language is {lang!r}", next="vedit guide render"
        )
    other = "en" if lang == "ar" else "ar"
    words = json.loads(f.read_text(encoding="utf-8"))
    cues = cuemod.build(words)
    if not cues:
        raise VeditError("the program transcription has no words", next="vedit joins")
    r = Report("subs")
    r.step(f"{project.slug}  ({root})")
    prompt = llm.load_prompt("subs")
    vars = {"context": llm.context(project), "src_lang": LANGS[lang], "tr_lang": LANGS[other]}
    src, tr, use = translate(
        cues, prompt, vars, ns.model, paths.vedit / "subs", paths.logs / "llm.jsonl", ns.force
    )
    lines = {lang: src, other: tr}
    out = root / "subs"
    out.mkdir(exist_ok=True)
    for code in ("ar", "en"):
        _write(out / f"{code}.srt", srt.render(cues, lines[code], rtl=code == "ar"))
    _write(out / "en.txt", " ".join(lines["en"][c["id"]] for c in cues) + "\n")
    state.record_stage(
        paths, "subs", hash_of(prompt.body, [c["text"] for c in cues], vars), [out / "ar.srt", out / "en.srt"]
    )
    longest = max(cues, key=lambda c: c["t1"] - c["t0"])
    dur = round(longest["t1"] - longest["t0"], 1)
    chars = max(len(c["text"]) for c in cues)
    models = sorted(set(use["models"]))
    r.ok_(f"{len(cues)} cues: longest {dur}s, widest {chars} chars; subs/ar.srt, subs/en.srt, subs/en.txt")
    r.info(f"{use['batches']} batches of {BATCH} ({use['cached']} cached)")
    if use["models"]:
        res = llm.Result([], use["models"], use["tokens_in"], use["tokens_out"], use["cost_usd"], use["seconds"],
                         use["fallbacks"], use["retries"])  # fmt: skip
        report_usage(r, res)
    r.data = {
        "cues": len(cues),
        "longest_s": dur,
        "batches": use["batches"],
        "cached_batches": use["cached"],
        "models": models,
        "files": [str(out / n) for n in ("ar.srt", "en.srt", "en.txt")],
        "cost_usd": round(use["cost_usd"], 4),
    }
    for n in ("ar.srt", "en.srt", "en.txt"):
        r.artifact(out / n, "subtitles")
    r.next = "vedit render  (captions go to YouTube with the video)"
    return r
