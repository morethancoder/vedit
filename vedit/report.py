"""Report object returned by command handlers (text or one JSON value), plus expected-failure errors."""

import os
import sys

# Ported from T scripts/_lib.sh: bold cyan step marker, green check, yellow bang, red cross.
BOLD, DIM, RED, GREEN, YELLOW, CYAN, RESET = (f"\033[{n}m" for n in (1, 2, 31, 32, 33, 36, 0))


def color_ok(stream=None) -> bool:
    """Colour only on a TTY with NO_COLOR unset (same test as _lib.sh)."""
    return bool((stream or sys.stdout).isatty()) and not os.environ.get("NO_COLOR")


# Stable error codes an agent branches on, with their process exit code (`vedit guide errors`).
CODES: dict[str, int] = {
    "failed": 1,  # the step ran and failed; read the message and the log
    "usage": 2,  # wrong command line; fix the flags (`vedit <cmd> --help`)
    "busy": 3,  # a job is running in this project; `vedit wait`, then retry
    "not_built": 4,  # an earlier step's output is missing; run the `next` command
    "stale": 4,  # an earlier step's output is out of date; run the `next` command
    "bad_input": 4,  # a file you wrote (cuts.yaml, cues.yaml, a flag value) is wrong; fix it
    "missing_tool": 5,  # ffmpeg / npx / studio / a model is not available; `vedit doctor`
    "no_disk": 5,  # not enough free space; `vedit clean`, then retry
    "timeout": 124,  # a time-boxed step ran out of time
}


def infer_code(message: str, next: str | None, exit: int | None) -> str:
    """The code of an error raised without one, from its exit code and wording (most raise sites)."""
    m, n = message.lower(), (next or "").lower()
    if exit == 2:
        return "usage"
    if exit == 124 or "timed out" in m:
        return "timeout"
    if "not enough disk" in m:
        return "no_disk"
    if "already running" in m or "job is running" in m or "is running (pid" in m:
        return "busy"
    if "stale" in m:
        return "stale"
    if "not built yet" in m or "is missing" in m or m.startswith("missing ") or "first" in n:
        return "not_built"
    if any(
        w in m for w in ("not found", "cannot read", "invalid", "unknown", "must ", "expected", "no such")
    ):
        return "bad_input"
    return "failed"


class VeditError(Exception):
    """Expected failure: message for the user, optional next command, a stable `code` and its exit code.
    Pass `code` where an agent would branch on it; otherwise it is inferred (`infer_code`)."""

    def __init__(
        self, message: str, next: str | None = None, exit: int | None = None, code: str | None = None
    ):
        super().__init__(message)
        if code is not None and code not in CODES:
            raise ValueError(f"unknown error code {code!r}")
        self.code = code or infer_code(message, next, exit)
        self.message, self.next = message, next
        self.exit = exit if exit is not None else CODES[self.code]

    def to_dict(self) -> dict:
        return {
            "v": 1,
            "ok": False,
            "error": self.message,
            "code": self.code,
            "next": self.next,
            "exit": self.exit,
        }


class Report:
    def __init__(self, command: str):
        self.command = command
        self.items: list[dict] = []
        self.data: dict = {}
        self.next: str | None = None
        self.artifacts: list[dict] = []

    def artifact(self, path, kind: str) -> "Report":
        """A file this run wrote that the caller will want (listed in the JSON as `artifacts`)."""
        self.artifacts.append({"path": str(path), "kind": kind})
        return self

    def _add(self, level: str, text: str) -> "Report":
        self.items.append({"level": level, "text": text})
        return self

    def step(self, text: str):
        return self._add("step", text)

    def ok_(self, text: str):
        return self._add("ok", text)

    def warn(self, text: str):
        return self._add("warn", text)

    def fail(self, text: str):
        return self._add("fail", text)

    def info(self, text: str):
        return self._add("info", text)

    @property
    def ok(self) -> bool:
        return not any(i["level"] == "fail" for i in self.items)

    def to_dict(self) -> dict:
        return {
            "v": 1,
            "command": self.command,
            "ok": self.ok,
            "artifacts": self.artifacts,
            "items": self.items,
            "data": self.data,
            "next": self.next,
        }

    def to_text(self, color: bool = False) -> str:
        c = (lambda s: s) if color else (lambda s: "")
        lines = []
        for i in self.items:
            t, lv = i["text"], i["level"]
            if lv == "step":
                lines.append(f"\n{c(BOLD + CYAN)}▸ {t}{c(RESET)}")
            elif lv == "ok":
                lines.append(f"{c(GREEN)}✓{c(RESET)} {t}")
            elif lv == "warn":
                lines.append(f"{c(YELLOW)}!{c(RESET)} {t}")
            elif lv == "fail":
                lines.append(f"{c(RED)}✗{c(RESET)} {t}")
            else:
                lines.append(t)
        if self.next:
            lines.append(f"{c(DIM)}next: {self.next}{c(RESET)}")
        return "\n".join(lines).lstrip("\n")


def confirm(question: str, yes: bool = False, destructive: bool = False) -> bool:
    """True on --yes. CI=1 auto-yes as in _lib.sh, except destructive asks, which refuse.

    Never hangs: no prompt when stdin is not a TTY (answer is no).
    """
    if yes:
        return True
    if os.environ.get("CI") == "1":
        return not destructive
    if not sys.stdin.isatty():
        return False
    try:
        reply = input(f"? {question} [y/N] ")
    except EOFError:
        return False
    return reply.strip().lower() in ("y", "yes")
