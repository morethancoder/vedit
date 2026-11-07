"""Fail if a tree (or a commit message) about to go public holds personal data.

Usage: python3 scripts/public_check.py <dir> [--message FILE]

Personal strings are read from this machine at run time and never written here: the account's full name
(`id -F`), the home folder, the git email, plus one extra term per line in ~/.config/vedit/public-scrub.
Also fails on: any home path, any real email address, secrets, video/recordings, media outside the style
packs, files over 2 MB, and private folders. Prints each problem; exit 1 if any.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

PRIVATE_PATHS = (".workflow-compare", "reference", ".claude", ".vedit", "tests/fixtures/clip-ar-10s")
STYLE_MEDIA = re.compile(r"^vedit/styles/[^/]+/(fonts/.+\.(woff2|ttf|otf)|logos/.+\.svg|sfx/.+\.mp3)$")
MEDIA = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".wav", ".m4a", ".aac", ".flac", ".mp3", ".ogg",
         ".png", ".jpg", ".jpeg", ".gif", ".webp", ".heic", ".svg", ".woff2", ".ttf", ".otf"}  # fmt: skip
MAX_BYTES = 2 * 1024 * 1024
OK_EMAIL = re.compile(r"@(users\.noreply\.github\.com|example\.(com|org)|anthropic\.com)$", re.IGNORECASE)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
HOME_PATH = re.compile(r"/(Users|home)/(?!runner\b|user\b|you\b|me\b|<)[A-Za-z0-9._-]+")
SECRETS = re.compile(
    r"(sk-ant-[A-Za-z0-9_-]{10,}|sk-[A-Za-z0-9]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}"
    r"|AIza[0-9A-Za-z_-]{30,}|xox[abp]-[A-Za-z0-9-]{10,}|-----BEGIN [A-Z ]*PRIVATE KEY-----"
    r"|\b\d{8,10}:[A-Za-z0-9_-]{35}\b)"  # last one: Telegram bot token
)


def _run(*cmd: str) -> str:
    try:
        return subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def personal() -> tuple[list[str], list[str]]:
    """(plain needles matched case-insensitively, name words matched as whole words)."""
    home = os.path.expanduser("~")
    email = _run("git", "config", "--global", "user.email") or _run("git", "config", "user.email")
    extra = Path(home, ".config", "vedit", "public-scrub")
    terms = [t.strip() for t in extra.read_text().splitlines() if t.strip()] if extra.exists() else []
    needles = [home, Path(home).name, *terms]
    if email and not OK_EMAIL.search(email):
        needles += [email, email.split("@")[0]]
    names = [w for w in _run("id", "-F").split() if len(w) >= 2]
    return [n for n in needles if len(n) >= 3], names


def check_text(label: str, text: str, needles: list[str], names: list[str], emails: bool = True) -> list[str]:
    bad = []
    low = text.lower()
    for n in needles:
        if n.lower() in low:
            bad.append(f"{label}: personal string (home, email or listed term)")
    for w in names:
        if re.search(r"\b" + re.escape(w) + r"\b", text):
            bad.append(f"{label}: the account holder's name")
    if HOME_PATH.search(text):
        bad.append(f"{label}: a home-folder path ({HOME_PATH.search(text).group(0)[:7]}…)")
    for m in EMAIL.finditer(text) if emails else ():
        if not OK_EMAIL.search(m.group(0)) and not m.group(0).endswith((".woff2", ".png", ".svg")):
            bad.append(f"{label}: an email address")
            break
    if SECRETS.search(text):
        bad.append(f"{label}: something that looks like a secret or token")
    return bad


def check_tree(root: Path, needles: list[str], names: list[str]) -> list[str]:
    bad = []
    for f in sorted(root.rglob("*")):
        rel = f.relative_to(root).as_posix()
        if rel == ".git" or rel.startswith(".git/") or not f.is_file():
            continue
        if any(rel == p or rel.startswith((p + "/", p + ".")) for p in PRIVATE_PATHS):
            bad.append(f"{rel}: private folder or file")
            continue
        if f.suffix.lower() in MEDIA and not STYLE_MEDIA.match(rel):
            bad.append(f"{rel}: media outside the style packs (recordings and pictures stay private)")
        if f.stat().st_size > MAX_BYTES:
            bad.append(f"{rel}: over 2 MB")
        if f.name == "uv.lock" or f.suffix.lower() in MEDIA - {".svg"}:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        # third-party code keeps its authors' published contact lines
        bad += check_text(rel, text, needles, names, emails=not rel.startswith("vedit/vendor/"))
    return bad


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    needles, names = personal()
    bad = check_tree(Path(argv[0]), needles, names)
    if "--message" in argv:
        msg = Path(argv[argv.index("--message") + 1]).read_text(encoding="utf-8")
        bad += check_text("commit message", msg, needles, names)
    for b in bad:
        print(f"  ✗ {b}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
