# Cut-outs for big words

The creator cut out of the program so a big word can sit behind his head.

Done when:
- [x] each big-number cue gets a matte over its program range, keyed by (range, cut hash), proxy and 4K variants
- [x] uses `studio cutout` for video when phase 06 ships; until then `hyperframes remove-background` + the shelf mask, marked `# TEMP(studio-cutout)`
- [x] at most one letter tucked behind the head; layout uses the pack's per-font advance table

## Refs

- port T `scripts/matte.sh`, `tools/matte_mask.py`, `build.py` `big_layout`
- `../phase-06-studio/step.md` (planned in Studio `plans/phase-20-vedit/feature-video-cutout.md`)
