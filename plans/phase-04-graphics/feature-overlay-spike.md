# Overlay-only render: measure first

Prove that rendering only the graphics (transparent, only where they're on screen) and compositing them onto
the program in ffmpeg beats rendering the whole film through Chrome. Its result decides how `compose`, `draft`
and `render` are built.

Done when:
- [x] on a copy of one ~150 s Telegram chunk (`~/Demos/tele-a7-growth-story/hf-render`, hyperframes@0.8.170), the full-frame 4K60 path and the overlay path are both rendered and timed on the same machine; wall time, frames rendered by Chrome, peak frame-cache disk and output size recorded in `docs/pipeline.md`
- [x] the transparent output HyperFrames can produce is found and named (ProRes 4444 / PNG frames / VP9 alpha) and which of them VideoToolbox decodes and encodes; the chosen intermediate written down
- [ ] the composite is checked against the full-frame render at 6 graphic peaks (behind-the-head big word, screen cue over blur, punch-in zoom, chapter card, doodle, end fade): no visible difference in a side-by-side sheet the creator looks at, and edges of transparent text don't fringe
  (agent-checked 2026-11-05: PSNR 39–49 dB, no fringe; sheet at
  `~/Demos/vedit-overlay-spike/out/contact-sheet.png`, waiting for the creator's look)
- [x] the decision is recorded in `plans/plan.md`: adopt overlay-only if it is clearly faster with equal output, otherwise keep full-frame and note why

## Approach

Layers, bottom to top: program (with punch-in zooms done in ffmpeg) → blur regions for screen cues →
graphics *behind* the creator (big words) → the creator cut-out → graphics *in front*. Chrome renders only the two graphics
layers, each only over its cue windows (merge windows closer than ~1 s); everything else is ffmpeg on
VideoToolbox. A frame with no graphic is never opened in Chrome.

This runs on the existing project with scripts in the spike folder (not vedit code), so it can start now,
in parallel with phases 01–03. Work on a copy; never write inside the Telegram project.

Results: [`spike-results.md`](spike-results.md). Two ranges (chunk 00 + chunk 05) because no chunk holds all
six types; the film has no screen-recording cue over blur.

## Refs

- `../../docs/pipeline.md` (render), `../../docs/traps.md` (VP9 alpha is CPU-only; colorkey chains)
- feeds: [`feature-compose.md`](feature-compose.md), [`../phase-08-output/feature-draft.md`](../phase-08-output/feature-draft.md), [`../phase-08-output/feature-render.md`](../phase-08-output/feature-render.md)
