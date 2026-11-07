# Phase 06: Studio additions

Add the local-AI capabilities vedit needs to Studio (`~/Projects/New/studio`), so no model lives in vedit.

Done when:
- [x] `studio cutout VIDEO` returns an alpha video of the main person, used by vedit's cut-outs
- [ ] vedit has no `# TEMP(studio-cutout)` markers left (the old-Studio fallback still carries them, 2026-11-05)

## Children

- [`feature-video-cutout.md`](feature-video-cutout.md) — person matte for video in Studio
- [`feature-batch-transcribe.md`](feature-batch-transcribe.md) [P] — optional: many short clips in one job

## Refs

- work happens in the Studio repo, following its own CLAUDE.md and plans; this phase tracks what vedit needs
- `../../docs/studio.md`
