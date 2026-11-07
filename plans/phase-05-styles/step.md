# Phase 05: Style packs and doodles

Make the look swappable: graphics come from packs, doodles from a library plus short scene specs.

Done when:
- [x] `yellow-doodle` and `claude-violet` packs render every v1 cue type
- [x] switching `style:` in cues.yaml changes the whole look with no other edit
- [ ] a new pack built from screenshots with `vedit style …`, picked by the creator from options, saved to a channel, drives a video

## Children

- [`feature-pack-format.md`](feature-pack-format.md) — pack.yaml, types/*.html slots, fallback to base, user packs
- [`feature-yellow-doodle.md`](feature-yellow-doodle.md) [P] — pack from the Telegram video (parallel with claude-violet)
- [`feature-claude-violet.md`](feature-claude-violet.md) [P] — pack from the Claude Code in Telegram video
- [`feature-doodle-library.md`](feature-doodle-library.md) — primitives, icons, scene specs, scene library
- [`feature-custom.md`](feature-custom.md) — `type: custom` escape hatch
- [`feature-style-library.md`](feature-style-library.md) — global/channel/built-in packs, keywords, `vedit styles find`, resolution order
- [`feature-style-authoring.md`](feature-style-authoring.md) — screenshots → draft pack → `try` / `fork` / `compare` / `pick` / `save` (after the two packs prove the format)

## Refs

- depends on: [`../phase-04-graphics/step.md`](../phase-04-graphics/step.md)
- `../../docs/formats.md` (style pack section)
