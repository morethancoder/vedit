#!/usr/bin/env bash
# Export HEAD as a scrubbed tree for the public repo: no personal data, one commit, noreply author.
# Usage: scripts/public.sh <out-dir>   (the dir is recreated). Publishing goes through scripts/publish.sh.
set -euo pipefail
source "$(dirname "$0")/_lib.sh"

out="${1:?usage: scripts/public.sh <out-dir>}"
root="$(git rev-parse --show-toplevel)"
step "export HEAD to $out"
rm -rf "$out" && mkdir -p "$out"
git -C "$root" archive HEAD | tar -x -C "$out"

step "drop private material"
# workflow-compare session records, the earlier projects' source, the clip of the creator's face and voice
rm -rf "$out/.workflow-compare" "$out/reference" "$out/.claude" "$out"/tests/fixtures/clip-ar-10s.*

printf '\n# generated stand-in for the unpublished speech clip (tests/conftest.py)\ntests/fixtures/clip-ar-10s.*\n' >> "$out/.gitignore"

step "scrub names and home paths"
# Personal strings come from this machine at run time (never written in this file): the account's full name
# (id -F), the home folder, the git email; plus one extra term per line in ~/.config/vedit/public-scrub.
python3 - "$out" "$(id -F 2>/dev/null || true)" "$HOME" "$(git -C "$root" config user.email || true)" <<'PY'
import re, sys
from pathlib import Path

root, full, home, email = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4]
extra = Path.home() / ".config" / "vedit" / "public-scrub"
names = [w for w in full.split() if len(w) >= 2]
terms = [t.strip() for t in extra.read_text().splitlines() if t.strip()] if extra.exists() else []
subs = [(re.compile(re.escape(home)), "~")]
if email:
    subs.append((re.compile(re.escape(email), re.I), "user@example.com"))
for n in names:
    start = r"(^|(?<=[.!?:]\s)|(?<=^- )|(?<=\*\*))"
    subs += [(re.compile(start + re.escape(n) + r"'s\b", re.M), r"\1The creator's"),
             (re.compile(start + re.escape(n) + r"\b", re.M), r"\1The creator"),
             (re.compile(r"\b" + re.escape(n) + r"'s\b"), "the creator's"),
             (re.compile(r"\b" + re.escape(n) + r"\b"), "the creator")]
for t in terms:
    subs.append((re.compile(re.escape(t), re.I), "the creator"))
n = 0
for f in root.rglob("*"):
    if not f.is_file() or f.suffix in {".mp3", ".woff2", ".ttf", ".png", ".jpg", ".mp4", ".wav", ".lock"}:
        continue
    try:
        text = f.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        continue
    new = text
    for rx, rep in subs:
        new = rx.sub(rep, new)
    if new != text:
        f.write_text(new, encoding="utf-8")
        n += 1
print(f"  scrubbed {n} files")
PY
step "check: nothing personal left"
python3 "$root/scripts/public_check.py" "$out" || die "personal data in the export (above): nothing was published"
ok "clean: no name, home path, email, secret or recording"
