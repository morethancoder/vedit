# Phase 06: Studio additions

Add the local-AI capabilities vedit needs to Studio (`~/Projects/New/studio`), so no model lives in vedit.

**The work is planned in Studio:** [`~/Projects/New/studio/plans/phase-20-vedit/`](../../../../New/studio/plans/phase-20-vedit/step.md)
(moved there 2026-11-08; Studio work follows Studio's CLAUDE.md and plans). This file only says what vedit needs.

Done when:
- [ ] `studio cutout VIDEO` is merged in Studio main and used by vedit's cut-outs (built on Studio branch
      `vedit/video-cutout`, not merged; Studio leaf `feature-video-cutout.md`)
- [ ] vedit has no `# TEMP(studio-cutout)` markers left (six in `vedit/graphics/cutouts.py`)
- [ ] optional: refine and listen use `studio transcribe --batch` when present (Studio leaf
      `feature-batch-transcribe.md`), keeping the one-WAV splice as fallback

## Refs

- `../../docs/studio.md`
