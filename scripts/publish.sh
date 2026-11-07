#!/usr/bin/env bash
# The only way vedit goes public. Exports HEAD scrubbed, tests it, checks it, commits it into the public clone
# (.public/) with the GitHub noreply author and pushes. Any personal data found stops it before the push.
# Usage: make publish MSG="what changed"
set -euo pipefail
source "$(dirname "$0")/_lib.sh"

REPO="morethancoder/vedit"
root="$(git rev-parse --show-toplevel)"
stage="$root/.public-stage"
pub="$root/.public"
msg="${MSG:-}"
[ -n "$msg" ] || die 'say what changed: make publish MSG="…"'

bash "$root/scripts/guard.sh" >/dev/null
[ -z "$(git -C "$root" status --porcelain --untracked-files=no -- . ':!.workflow-compare')" ] ||
  warn "uncommitted changes are not published (the export is HEAD $(git -C "$root" rev-parse --short HEAD))"

bash "$root/scripts/public.sh" "$stage"

step "tests on the export (no private clip)"
# the venv and bytecode stay outside the export, so only the scrubbed tree reaches .public/
(cd "$stage" && UV_PROJECT_ENVIRONMENT="$root/.public-venv" PYTHONDONTWRITEBYTECODE=1 \
  uv run --quiet pytest -q -p no:cacheprovider 2>&1 | tail -1) | tee "$stage/.tests"
grep -qE "^[0-9]+ passed" "$stage/.tests" && ! grep -q "failed" "$stage/.tests" || die "tests fail on the export"
rm -f "$stage/.tests"; rm -f "$stage"/tests/fixtures/clip-ar-10s.*
extra="$(cd "$stage" && find . \( -name __pycache__ -o -name .venv -o -name .pytest_cache -o -name '*.egg-info' \) | head -5)"
[ -z "$extra" ] || die "the test run left files in the export: $extra"

step "sync into the public clone"
if [ ! -d "$pub/.git" ]; then
  rm -rf "$pub" && gh repo clone "$REPO" "$pub" -- -q
fi
url="$(git -C "$pub" remote get-url origin)"
[[ "$url" == *"github.com/$REPO"* || "$url" == *"github.com:$REPO"* ]] || die ".public points at $url, not $REPO"
bash "$root/scripts/guard.sh" >/dev/null   # (re)install the public clone's pre-push check
git -C "$pub" pull -q --ff-only origin main
rsync -a --delete --exclude .git "$stage/" "$pub/"
rm -rf "$stage"

step "check the public tree and the message"
printf '%s\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n' "$msg" > "$pub/.git/PUBLISH_MSG"
python3 "$root/scripts/public_check.py" "$pub" --message "$pub/.git/PUBLISH_MSG" || die "personal data found: nothing was pushed"
git -C "$pub" add -A
if git -C "$pub" diff --cached --quiet; then ok "nothing changed since the last publish"; exit 0; fi
git -C "$pub" diff --cached --stat | tail -15

id="$(gh api user --jq .id)"; login="$(gh api user --jq .login)"
export GIT_AUTHOR_NAME="$login" GIT_COMMITTER_NAME="$login"
export GIT_AUTHOR_EMAIL="$id+$login@users.noreply.github.com" GIT_COMMITTER_EMAIL="$id+$login@users.noreply.github.com"
git -C "$pub" -c commit.gpgsign=false commit -q -F "$pub/.git/PUBLISH_MSG"

step "push"
git -C "$pub" push -q origin main
ok "published $(git -C "$pub" rev-parse --short HEAD) to https://github.com/$REPO"
