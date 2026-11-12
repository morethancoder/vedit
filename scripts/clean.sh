#!/usr/bin/env bash
# Remove what testing and building leave behind; everything removed rebuilds itself. Prints what was freed.
#   1. repo caches: .pytest_cache, .ruff_cache, __pycache__, build output, publish staging (.public-stage, .public-venv)
#   2. pytest's temp folders ($TMPDIR/pytest-of-$USER)
#   3. `vedit clean` (caches only, never renders, originals or your files) on every project in PROJECTS
#      (default: config.yaml's `projects:` folder; PROJECTS= to skip)
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/_lib.sh

free_gb() { df -k "$HOME" | awk 'NR==2 {printf "%.1f", $4 / 1048576}'; }
before=$(free_gb)

step "repo caches"
paths=(.pytest_cache .ruff_cache build dist .public-stage .public-venv)
while IFS= read -r p; do paths+=("$p"); done < <(
  find . \( -path ./.venv -o -path ./.git -o -path ./.public \) -prune -o \
    \( -name __pycache__ -o -name '*.egg-info' \) -type d -print
)
tmp="$(python3 -c 'import tempfile; print(tempfile.gettempdir())')"
paths+=("$tmp/pytest-of-$(id -un)")

total=0
for p in "${paths[@]}"; do
  [ -e "$p" ] || continue
  kb=$(du -sk "$p" 2>/dev/null | awk '{print $1}')
  rm -rf "$p"
  total=$((total + kb))
done
ok "removed $(( total / 1024 )) MB of caches and temp folders"

if [ -z "${PROJECTS+set}" ]; then
  PROJECTS="$(uv run --quiet python -c \
    'from pathlib import Path; from vedit import channel; p = channel.load_config().get("projects"); print(Path(p).expanduser() if p else "")')"
fi
if [ -n "$PROJECTS" ] && [ -d "$PROJECTS" ]; then
  step "vedit clean in $PROJECTS"
  found=0
  for y in "$PROJECTS"/*/project.yaml; do
    [ -f "$y" ] || continue
    found=1
    d="$(dirname "$y")"
    line="$(uv run --quiet vedit clean --yes --project "$d" 2>&1 | grep -E 'freed|nothing|refuse|running' | tail -1 || true)"
    say "  $(basename "$d"): ${line:-done}"
  done
  [ "$found" = 1 ] || say "  no vedit projects there"
else
  say "no projects folder (set projects: in config.yaml, or PROJECTS=dir)"
fi

ok "free space: ${before} GB -> $(free_gb) GB (renders and originals are kept; vedit clean --posted removes those)"
