# vedit render

The 4K60 master, safe to leave running.

Done when:
- [x] 4K program + 4K cut-outs, then ~150 s chunks cut where only the A-roll shows; each with its own frame cache, deleted after
- [x] runs detached; progress (stage, chunk, frame) in `.vedit/state.json`; a rerun resumes from finished chunks
- [x] ~~overlay mode~~ not adopted (spike: 1.16x, `docs/pipeline.md`): full-frame is the only path, so no `--full`
      flag; chunk HTMLs are written by `vedit build` (`.vedit/hf/chunks/`), never re-planned at render time
- [x] lossless video join, audio from chunk PCM in one AAC 320k pass, `+faststart`; verify frames = duration × 60; checks free disk first

## Refs

- [`../phase-04-graphics/feature-overlay-spike.md`](../phase-04-graphics/feature-overlay-spike.md) (measured numbers, chosen alpha intermediate)
- port T `scripts/render.sh` and `media.sh` full half; numbers in `../../docs/pipeline.md`
