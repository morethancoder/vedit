# Traps already hit (don't repeat)

Moved from the `youtube-edit` skill. Each one cost real time once; the code should make it impossible.

## Transcription and cutting
- ASR word times drift up to ~0.5 s: never cut on raw word times; refine by listening (docs/pipeline.md).
- whisper.cpp looped across splices without `-mc 0`; Studio's qwen3-asr doesn't, but keep splice gaps of 2 s.
- Whisper rewrote Iraqi Arabic toward formal Arabic, so words didn't match audio and cuts landed wrong.
- A "filler" cut once dropped a "ما" and flipped the meaning ("I had knowledge"). Join checks compare meaning-bearing words.
- Cap exports may already be pause-trimmed; Cap C-style exports can mirror the camera and switch layout on the last word.

## Shell and tools
- `npx` swallows stdin in `while read` loops: run every subprocess with stdin closed.
- zsh doesn't word-split `$var`.
- ffmpeg `colorkey` twice in one chain overwrites the first key's alpha: key, overlay on black, key again.
- `uv run python -I` hides the script's own folder (sibling imports fail). Moot once vedit is a package.
- Bare ffmpeg calls are blocked by a hook: always `timeout <s> nice -n 19 ffmpeg …`.

## Faces and cut-outs
- Face track rows are every N frames, not exactly 0.25 s: index by the real spacing.
- `hyperframes remove-background` keeps the bookshelf beside his head: always limit the matte to a head ellipse
  around the tracked face plus everything below the chin, feathered (`matte_mask.py`).
- VP9 with alpha has no VideoToolbox encoder: those short clips encode on the CPU.
- Cut-out staleness is keyed on the cut (hash of edl pieces) and range, never file dates.
- Thumbnail cut-outs: the shelf can touch his ear, so drop shelf-coloured pixels (cool purple, R−B < −6) beside the
  head instead of a straight cut (that clipped ear and hair). Check every cut-out over red at full size.

## HyperFrames
- Every `<audio>` needs `data-duration`; one `tl.set` baseline before repeated tweens of one element; guard tweens
  of optional elements; one sub-composition file per overlay (don't rely on per-instance vars).
- `backdrop-filter` stops working inside any ancestor with opacity < 1.
- Edits made in HyperFrames Studio to generated files are overwritten by the next build.

## Subtitles
- When the cut changes, rebuild cues from the new program transcription; mapping old cues only works if no
  words were added back or removed.
- YouTube rejects `<` and `>` in descriptions: write `YOUR_TOKEN`, not `<token>`.

## Long jobs
- 2026-11-05: the agent stopped polling mid-render while `render.sh` kept running detached; the creator thought it was
  stuck and paid for another session. vedit writes progress to `.vedit/state.json` and `vedit status` reads it.
- A polling loop of `pgrep -f "<script>"` matches its own command line and never exits: wait on the PID.
