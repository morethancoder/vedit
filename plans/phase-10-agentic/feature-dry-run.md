# --dry-run

See what a step would do before it spends minutes or disk.

Done when:
- [ ] global `--dry-run` on `cut`, `build`, `draft`, `render`, `subs`, `clean`, `new`: reports the plan (pieces or
      chunks to render vs reused, files to write or delete with sizes, disk needed, model calls) and exits 0
      without writing anything (a test checks the project tree is byte-identical after)
- [x] commands without a meaningful dry run reject it with code `usage`

(open: done for `render`, `draft`, `clean`, with a test that the tree is unchanged; `cut`, `build`, `subs`,
`new` still to do: their plans need the listening cache, cue resolve and the router's batch cache without writing.)
