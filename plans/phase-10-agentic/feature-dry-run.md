# --dry-run

See what a step would do before it spends minutes or disk.

Done when:
- [x] global `--dry-run` on `cut`, `build`, `draft`, `render`, `subs`, `clean`, `new`: reports the plan (pieces or
      chunks to render vs reused, files to write or delete with sizes, disk needed, model calls) and exits 0
      without writing anything (a test checks the project tree is byte-identical after)
- [x] commands without a meaningful dry run reject it with code `usage`

Done 2026-11-07 for all seven; tests/test_dry_run.py checks each leaves the tree unchanged (size + mtime of
every file). On the acceptance copy: `cut` 13:08.70 / 161 pieces all reused, `subs` 5 batches cached, `build`
48 pages to write (pages.py changed since that build), the tree unchanged after each. `build --plan` no longer
saves the brightness cache.
