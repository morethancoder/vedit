# Phase 04: Graphics engine

Turn `cues.yaml` into a checked HyperFrames project, with every placement decision made in code.

Done when:
- [x] `vedit build` writes `.vedit/hf/` from cues.yaml + the style pack and `hyperframes check` passes
- [x] no generated graphic overlaps the face track, crosses a shot change, or has a box behind its text

## Children

- [`feature-overlay-spike.md`](feature-overlay-spike.md) [P] — measure overlay-only vs full-frame render on one Telegram chunk; decides compose/draft/render (can start now, parallel with phases 01–03)
- [`feature-cues-file.md`](feature-cues-file.md) — cues.yaml loader, word anchors, chapters from cuts.yaml
- [`feature-faces.md`](feature-faces.md) [P] — face track + `cam` flag (parallel with cues-file)
- [`feature-placement.md`](feature-placement.md) — fit-in-shot, side from faces, theme from brightness, blur
- [`feature-cutouts.md`](feature-cutouts.md) — person cut-outs for big words (Studio, temporary fallback)
- [`feature-compose.md`](feature-compose.md) — hosts, index.html, zooms, SFX, fade, lint/check

## Refs

- depends on: [`../phase-03-cut/step.md`](../phase-03-cut/step.md); the overlay spike depends on nothing
- the cue type templates come from phase 05; build here against a minimal base pack first
