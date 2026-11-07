#!/usr/bin/env bash
# Remove build output and caches that rebuild themselves; print what was freed.
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/_lib.sh

paths=(.pytest_cache .ruff_cache build dist)
while IFS= read -r p; do paths+=("$p"); done < <(
  find . \( -path ./.venv -o -path ./.git \) -prune -o \
    \( -name __pycache__ -o -name '*.egg-info' \) -type d -print
)

total=0
for p in "${paths[@]}"; do
  [ -e "$p" ] || continue
  kb=$(du -sk "$p" 2>/dev/null | awk '{print $1}')
  rm -rf "$p"
  ok "removed $p (${kb} KB)"
  total=$((total + kb))
done
say "freed ${total} KB"
