#!/usr/bin/env bash
# Install the git hooks that keep personal data out of the public repo (safe to re-run).
#  - this repo: pre-push refuses every push (its history holds personal data)
#  - .public/:  pre-push re-checks every pushed commit (tree, message, author) before it leaves
set -euo pipefail
source "$(dirname "$0")/_lib.sh"
root="$(git rev-parse --show-toplevel)"
hooks="$(git -C "$root" rev-parse --git-path hooks)"; [[ "$hooks" = /* ]] || hooks="$root/$hooks"
install -m 755 "$root/scripts/hooks/pre-push-private" "$hooks/pre-push"
ok "private repo: pushes refused"
if [ -d "$root/.public/.git" ]; then
  sed "s|@CHECKER@|$root/scripts/public_check.py|" "$root/scripts/hooks/pre-push-public" > "$root/.public/.git/hooks/pre-push"
  chmod 755 "$root/.public/.git/hooks/pre-push"
  ok "public clone: every push re-checked"
fi
