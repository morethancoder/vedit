"""Model router: one saved prompt, the cheapest model that can do it, validated JSON, fallback on failure.

Order for `auto`: the prompt's preferred model, then the rest of Haiku -> Sonnet -> gemma4 cloud (docs/models.md).
Claude runs through `claude -p` (the creator's subscription) with Claude Code's own system prompt, tools, MCP servers
and settings switched off, so a call costs the prompt and nothing else (~0.9K overhead instead of ~48K).
gemma runs through Ollama's /api/chat with `format: json`. Every call is logged to .vedit/logs/llm.jsonl.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

from vedit.report import VeditError
from vedit.run import run

# name -> (backend, model id). Ids from the claude-api skill (2026-11); gemma via the local Ollama daemon.
MODELS: dict[str, tuple[str, str]] = {
    "haiku": ("claude", "claude-haiku-5-5"),
    "sonnet": ("claude", "claude-sonnet-5-5"),
    "gemma": ("ollama", "gemma4:31b-cloud"),
}
ORDER = ["haiku", "sonnet", "gemma"]
TRIES = 3  # per batch per model, for invalid output; a limit or a CLI failure moves on at once
OLLAMA_URL = "http://localhost:11434/api/chat"
SYSTEM = (
    "You are a careful video-editing assistant. Reply with one JSON value only: no prose, no code fences."
)
LIMIT_RE = re.compile(r"rate.?limit|usage limit|weekly limit|quota|overloaded|429|529|credit", re.IGNORECASE)


class LlmError(VeditError):
    """Every model in the chain failed."""


class Invalid(Exception):
    """The model answered, but not with what the prompt's schema asks for."""


class Unavailable(Exception):
    """The model could not answer (CLI error, limit, daemon down); try the next one."""


@dataclass
class Prompt:
    name: str
    model: str
    schema: dict
    body: str
    batch: int = 0  # transcript lines per call; 0 = the whole input in one call
    effort: str | None = None
    timeout: float = 600
    meta: dict = field(default_factory=dict)

    def render(self, **vars) -> str:
        def sub(m):
            key = m.group(1)
            if key not in vars:
                raise VeditError(f"prompt {self.name}: no value for {{{{{key}}}}}")
            return str(vars[key])

        return re.sub(r"\{\{(\w+)\}\}", sub, self.body)


def prompts_dir() -> Path:
    return Path(str(resources.files("vedit") / "prompts"))


def prompt_names() -> list[str]:
    return sorted(p.stem for p in prompts_dir().glob("*.md"))


def load_prompt(name: str) -> Prompt:
    """vedit/prompts/<name>.md: `---` header (model, schema as one-line JSON, batch, effort), then the body."""
    f = prompts_dir() / f"{name}.md"
    if not f.is_file():
        raise VeditError(f"no prompt {name!r} (have: {', '.join(prompt_names())})", next="vedit llm")
    text = f.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise VeditError(f"{f}: missing --- header")
    head, _, body = text[4:].partition("\n---\n")
    meta = {}
    for line in head.splitlines():
        k, _, v = line.partition(":")
        if k.strip():
            meta[k.strip()] = v.strip()
    try:
        schema = json.loads(meta.get("schema", "{}"))
    except ValueError as e:
        raise VeditError(f"{f}: schema is not JSON: {e}") from e
    model = meta.get("model", "haiku")
    if model not in MODELS:
        raise VeditError(f"{f}: unknown model {model!r} (have: {', '.join(MODELS)})")
    return Prompt(
        name=name,
        model=model,
        schema=schema,
        body=body.strip() + "\n",
        batch=int(meta.get("batch", 0) or 0),
        effort=meta.get("effort") or None,
        timeout=float(meta.get("timeout", 600)),
        meta=meta,
    )


# ---- validation: the subset of JSON Schema the prompts use (type, required, properties, items, enum) ----

_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
}


def validate(value, schema: dict, where: str = "$") -> None:
    t = schema.get("type")
    if t:
        ok = isinstance(value, _TYPES[t]) and not (t in ("number", "integer") and isinstance(value, bool))
        if not ok:
            raise Invalid(f"{where}: expected {t}, got {type(value).__name__}")
    if "enum" in schema and value not in schema["enum"]:
        raise Invalid(f"{where}: {value!r} not in {schema['enum']}")
    if isinstance(value, dict):
        for k in schema.get("required", []):
            if k not in value:
                raise Invalid(f"{where}: missing {k!r}")
        for k, sub in schema.get("properties", {}).items():
            if k in value:
                validate(value[k], sub, f"{where}.{k}")
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            validate(item, schema["items"], f"{where}[{i}]")


def parse_json(text: str):
    """The JSON value in a reply, tolerating code fences or a line of prose around it."""
    s = text.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s)
    try:
        return json.loads(s)
    except ValueError:
        pass
    starts = [i for i in (s.find("{"), s.find("[")) if i >= 0]
    if starts:
        i = min(starts)
        j = max(s.rfind("}"), s.rfind("]"))
        if j > i:
            try:
                return json.loads(s[i : j + 1])
            except ValueError as e:
                raise Invalid(f"reply is not JSON: {e}") from e
    raise Invalid("reply has no JSON")


# ---- backends ----


@dataclass
class Reply:
    text: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0


def call_claude(model_id: str, prompt: str, effort: str | None, timeout: float) -> Reply:
    cmd = ["claude", "-p", "--model", model_id, "--tools", "", "--output-format", "json"]
    cmd += ["--system-prompt", SYSTEM, "--strict-mcp-config", "--disable-slash-commands"]
    cmd += ["--setting-sources", "", "--no-session-persistence"]
    if effort:
        cmd += ["--effort", effort]
    proc = run([*cmd, prompt], int(timeout), check=False)  # the timeout wrapper takes whole seconds
    out = proc.stdout or ""
    try:
        d = json.loads(out)
    except ValueError:
        tail = (proc.stderr or out).strip()[-300:]
        raise Unavailable(f"claude exit {proc.returncode}: {tail or 'no output'}") from None
    if proc.returncode != 0 or d.get("is_error"):
        msg = str(d.get("result") or d.get("api_error_status") or f"exit {proc.returncode}")
        kind = "limit" if LIMIT_RE.search(msg) else "error"
        raise Unavailable(f"{kind}: {msg[:300]}")
    u = d.get("usage") or {}
    tin = sum(
        u.get(k, 0) or 0 for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    )
    used = next(iter(d.get("modelUsage") or {}), model_id)
    return Reply(
        d.get("result") or "", used, tin, u.get("output_tokens", 0) or 0, d.get("total_cost_usd") or 0.0
    )


def call_ollama(model_id: str, prompt: str, effort: str | None, timeout: float) -> Reply:
    body = {
        "model": model_id,
        "stream": False,
        "format": "json",
        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        OLLAMA_URL, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="replace")[:300]
        raise Unavailable(
            f"{'limit' if e.code == 429 or LIMIT_RE.search(msg) else 'error'}: ollama {e.code} {msg}"
        )
    except (OSError, ValueError) as e:
        raise Unavailable(f"error: ollama: {e}") from None
    text = (d.get("message") or {}).get("content") or ""
    return Reply(text, model_id, d.get("prompt_eval_count", 0) or 0, d.get("eval_count", 0) or 0)


BACKENDS = {"claude": call_claude, "ollama": call_ollama}


# ---- the router ----


def chain(prompt: Prompt, force: str | None = None) -> list[str]:
    if force and force != "auto":
        if force not in MODELS:
            raise VeditError(f"unknown model {force!r} (auto, {', '.join(MODELS)})")
        return [force]
    return ORDER[ORDER.index(prompt.model) :]


def batches(text: str, size: int) -> list[str]:
    lines = text.splitlines()
    if size <= 0 or len(lines) <= size:
        return [text]
    return ["\n".join(lines[i : i + size]) + "\n" for i in range(0, len(lines), size)]


def _log(log: Path | None, entry: dict) -> None:
    if log is None:
        return
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


@dataclass
class Result:
    values: list  # one validated JSON value per batch
    models: list[str]  # model that answered each batch
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    seconds: float = 0.0
    fallbacks: list[str] = field(default_factory=list)  # a model gave up and the next one answered
    retries: list[str] = field(default_factory=list)  # the same model answered after an invalid reply


def ask(
    prompt: Prompt,
    input: str,
    *,
    vars: dict | None = None,
    model: str | None = None,
    log: Path | None = None,
    check=None,
) -> Result:
    """Run `prompt` over `input` (split into batches of lines), one validated JSON value per batch.

    `check(value, batch_text)` may raise Invalid for checks the schema cannot express (ids round-trip,
    words copied from the batch); it counts as an invalid reply and is retried like one.
    """
    names = chain(prompt, model)
    res = Result([], [])
    t_all = time.monotonic()
    for bi, text in enumerate(batches(input, prompt.batch)):
        full = prompt.render(**(vars or {}), input=text)
        why, done, retry_note = None, False, ""
        for name in names:
            backend, mid = MODELS[name]
            for attempt in range(1, TRIES + 1):
                t0, rep = time.monotonic(), Reply("", mid)
                entry = {
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    "prompt": prompt.name,
                    "batch": bi,
                    "model": name,
                    "try": attempt,
                    "fallback": why,
                }
                try:
                    rep = BACKENDS[backend](mid, full + retry_note, prompt.effort, prompt.timeout)
                    res.tokens_in += rep.tokens_in
                    res.tokens_out += rep.tokens_out
                    res.cost_usd += rep.cost_usd
                    entry.update(id=rep.model, tokens_in=rep.tokens_in, tokens_out=rep.tokens_out)
                    entry["cost_usd"] = round(rep.cost_usd, 6)
                    value = parse_json(rep.text)
                    validate(value, prompt.schema)
                    if check:
                        check(value, text)
                except Unavailable as e:
                    why = f"{name}: {e}"
                    _log(
                        log, {**entry, "ok": False, "error": str(e), "secs": round(time.monotonic() - t0, 2)}
                    )
                    break  # a limit or a dead backend will not fix itself in a retry
                except Invalid as e:
                    why = f"{name}: invalid output ({e})"
                    secs = round(time.monotonic() - t0, 2)
                    _log(log, {**entry, "ok": False, "error": str(e), "secs": secs, "reply": rep.text[:400]})
                    # Say what was wrong: an identical retry tends to fail the same way.
                    retry_note = f"\n\nYOUR PREVIOUS REPLY WAS REJECTED: {e}. Reply again with exactly the shape asked for."
                    continue
                _log(log, {**entry, "ok": True, "secs": round(time.monotonic() - t0, 2)})
                res.values.append(value)
                res.models.append(name)
                if why and name != names[0]:
                    res.fallbacks.append(why)
                elif why:
                    res.retries.append(why)
                done = True
                break
            if done:
                break
        if not done:
            raise LlmError(
                f"{prompt.name}: batch {bi + 1}: every model failed (last: {why})",
                next="vedit llm  (to list prompts; or retry later; see .vedit/logs/llm.jsonl)",
            )
    res.seconds = time.monotonic() - t_all
    return res


# ---- inputs every drafting prompt shares ----

LINE_WORDS = 12  # words per transcript line given to a model (T's prompts used ~12)


def transcript(project, words_by_clip: dict[str, list[dict]] | None = None) -> str:
    """`[A 12.6] words ...` lines over every clip, the form every drafting prompt reads."""
    from vedit.commands.transcribe import lines
    from vedit.words import load

    out = []
    for clip in sorted(project.sources):
        ws = words_by_clip[clip] if words_by_clip else load(project.paths, clip)
        for g in lines(ws, maxw=LINE_WORDS):
            out.append(f"[{clip} {g[0]['t0']:.1f}] " + " ".join(w["w"] for w in g))
    return "\n".join(out) + "\n"


def context(project, notes: str | None = None) -> str:
    """What the model should know about the video: language, names, and the speaker's own outline."""
    lang = project.lang + (f" ({project.dialect} dialect)" if project.dialect else "")
    parts = [f"Spoken language: {lang}."]
    if project.hint:
        parts.append(f"Names and terms that occur: {project.hint}.")
    if notes:
        parts.append("Speaker's own outline (on his screen while recording):\n" + notes.strip())
    return "\n".join(parts)
