# Outputs

A project lists what it produces.

Done when:
- [x] `project.yaml` `outputs:` entries: `id`, `kind` (master | clip | short | story | post), `aspect`, `platforms`,
      `range` (word anchors `from`/`to`, clips only), `captions` (burned | srt | none; default by kind)
- [x] a project with no `outputs:` behaves exactly as before (one 16:9 YouTube master)
- [x] `vedit output add|list|rm` edits the list with checks (aspect known, range resolves to words)
