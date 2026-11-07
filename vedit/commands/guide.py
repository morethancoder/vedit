"""vedit guide [topic]: the built-in manual, pages shipped in vedit/guide/*.md."""

from importlib import resources

from vedit.report import Report, VeditError

NOT_TOPICS = {"overview", "skill"}
EPILOG = "example: vedit guide cuts"


def add_args(sp) -> None:
    sp.add_argument("topic", nargs="?", help="topic name (see --list); omit for the one-screen overview")
    sp.add_argument("--list", action="store_true", help="list topics, one line each")
    sp.epilog = EPILOG


def _dir():
    return resources.files("vedit") / "guide"


def read_page(name: str) -> tuple[dict, str]:
    """(front matter, body) of vedit/guide/<name>.md; front matter is flat `key: value` lines."""
    text = (_dir() / f"{name}.md").read_text(encoding="utf-8")
    meta: dict = {}
    if text.startswith("---\n"):
        head, _, body = text[4:].partition("\n---\n")
        for line in head.splitlines():
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
        text = body
    return meta, text


def topics() -> list[str]:
    names = sorted(p.name[:-3] for p in _dir().iterdir() if p.name.endswith(".md"))
    return [n for n in names if n not in NOT_TOPICS]


def loop_lines() -> list[str]:
    """The edit loop, rendered from the COMMANDS table so built/unbuilt marks never go stale."""
    from vedit.cli import COMMANDS, LOOP

    out = []
    for step in LOOP:
        if step.startswith("write "):
            out.append(f"  -> you write {step[6:]}")
            continue
        _, text, module = COMMANDS[step]
        out.append(f"  vedit {step:<12} {text}" + ("" if module else "  (not built yet)"))
    return out


def render(name: str) -> tuple[dict, str]:
    meta, body = read_page(name)
    body = body.replace("{{loop}}", "\n".join(loop_lines()))
    body = body.replace("{{topics}}", ", ".join(topics()))
    return meta, body.strip("\n")


def run(ns) -> Report:
    r = Report("guide")
    if ns.list:
        rows = {t: read_page(t)[0].get("summary", "") for t in topics()}
        for t, s in rows.items():
            r.info(f"{t:<16} {s}")
        r.data = {"topics": rows}
        r.next = "vedit guide <topic>"
        return r
    name = ns.topic or "overview"
    if name not in {*topics(), "overview"}:
        raise VeditError(f"no guide topic '{ns.topic}'", next="vedit guide --list")
    meta, body = render(name)
    r.info(body)
    r.data = {"topic": name, "text": body}
    r.next = meta.get("next") or "vedit guide --list"
    return r
