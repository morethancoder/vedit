# status and doctor

Know where a project stands, and whether the machine can run it, in one command each.

Done when:
- [x] `vedit status` prints each stage (ingest, transcribe, cut, build, render) as done / stale / missing, and a running render's chunk + frame progress from `.vedit/state.json`
- [x] `vedit doctor` checks ffmpeg with VideoToolbox, node/npx, pinned hyperframes, Studio status + qwen3-asr, Ollama (optional), free disk vs the next stage's need
- [x] a detached job that died shows as failed with the last log lines, not as running

## Approach

`state.json` is written by long jobs (pid, stage, progress, started, log path). Status checks the pid is
alive. Stale = recorded input hash differs from the current one.

## Refs

- `../../docs/traps.md` (the 2026-11-05 "stuck render")
