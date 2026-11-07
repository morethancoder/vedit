---
summary: draft, subtitles, 4K60 render, long jobs, clean-up
next: vedit status
---
# Render, subtitles, clean-up

## Commands

- `vedit draft`: 1080p draft of the same full-frame composition the master renders, written to
  `.vedit/renders/draft.mp4` and opened in QuickTime; reused while the build is unchanged. Use it for every
  review. `--force`, `--no-open`.
- `vedit subs`: writes `subs/ar.srt`, `subs/en.srt` and `subs/en.txt` (kept folder) from the final program's
  words. Cues are at most 84 characters and 6 s, split on pauses of 0.6 s. A model (Sonnet through the router,
  batches of 40 cues, ids must round-trip) cleans the speech-recognition text and translates it; results are
  cached per batch, so a rerun costs nothing. Product names, commands and file names stay in Latin letters in
  both files. Arabic lines start with U+200F and tokens that start with a symbol (`.env`, a dash option)
  get U+200E. Rerun it when the cut changes (cues are rebuilt from the new words). For an English project the
  source is `en.srt` and the translation `ar.srt`. `--model M`, `--force`.
- `vedit render`: 4K60 master to `.vedit/renders/master.mp4`. Run it only when the draft is approved. Order:
  4K program, 4K cut-outs, then ~150 s chunks (cut where only the A-roll shows), each with its own frame cache
  deleted after; video joined losslessly, one AAC 320k pass, checked (frames = duration x 60, 3840x2160). It
  checks free disk first and refuses while another job runs. `--wait` runs in the foreground. A chunk is
  reused only while its composition, assets and the 4K program are unchanged. While it runs, `vedit build` and
  `vedit cut` refuse (they would change files it reads); stop it with `kill <pid>` from `vedit status`.
- `vedit clean`: removes frame caches, render chunks, scratch audio/images and review caches under `.vedit/` and
  prints the space freed per path and in total. It refuses while a job runs. `vedit clean --posted` (only after
  the upload is posted) also deletes renders, proxies, program, cut-out mattes and the originals: plain `file:`
  sources, and for importer sources the recorder project (`origin:`, or what the importer's `originals()` names).
  Edited videos outside a recorder project are listed as kept (often clones that free about 0). It lists every
  path with its size and asks first (no TTY: lists and stops unless `--yes`); `--dry-run` only lists. Kept always: cuts.yaml,
  cues.yaml, custom/, subs/, youtube/, transcripts, words, edl.

## Long jobs

- A render runs detached and logs to `.vedit/logs/`. Progress is in `.vedit/state.json`.
- Poll with `vedit status`. Do not restart a running job; a job that stopped is shown with its log tail.
- Re-running `vedit render` resumes: finished chunks whose inputs did not change are kept.
- Never wait with `pgrep -f`: it matches its own command line and never ends.

## Encoding

All encodes use the Apple Silicon hardware encoders (VideoToolbox). The only CPU encode is VP9 with alpha.
