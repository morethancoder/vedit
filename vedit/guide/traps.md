---
summary: mistakes already made once; the code prevents them
next: vedit status
---
# Traps already hit

Each cost real time once. vedit handles them; do not work around it.

## Transcription and cutting

- ASR word times drift up to about 0.5 s: cut points are refined by listening, never taken from raw times.
- Iraqi Arabic gets rewritten toward formal Arabic by some models, so words stop matching the audio. Use the
  dialect set in project.yaml.
- A "filler" cut once dropped a "ما" and flipped the meaning. Join checks compare meaning-bearing words.
- A recorder's export may already be pause-trimmed or mirror the camera; an importer that reads the recorder's
  project gives vedit the clean camera and trims instead (`vedit guide importers`).
- When the cut changes, cues anchored to words follow; if you add words back, re-check the cues near them.

## Faces and cut-outs

- Cut-outs keep only a head ellipse plus everything below the chin, feathered: the bookshelf beside the head
  does not survive.
- Cut-out staleness is keyed on the cut and range, never on file dates.

## HyperFrames and generated files

- Edits to anything under `.vedit/` (including HyperFrames files) are overwritten by the next build. Edit
  cues.yaml, a style pack or `custom/` instead.
- Backdrop blur stops working inside any parent with opacity below 1. Templates already avoid it; a `custom`
  graphic must too.
- Every audio element needs a duration; a `custom` graphic is one sub-composition file.

## Shell

- Subprocesses run with stdin closed (`npx` otherwise swallows it) and under `timeout` and `nice`.
- YouTube rejects angle brackets in descriptions: write `YOUR_TOKEN`, not a bracketed token.
- A long render outlives the agent's polling. Use `vedit status`; see `vedit guide render`.
