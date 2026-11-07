# Pack format

One folder per look; the engine only knows slots and tokens.

Done when:
- [x] `pack.yaml` declares colours, fonts (files bundled), shadows, motion (eases, durations), SFX map, advance tables
- [x] each `types/<type>.html` declares its slots; the engine fills them and validates cues against them
- [x] packs load from `vedit/styles/` and `~/.config/vedit/styles/`; a missing type falls back to `base`; `vedit styles` lists packs and their types

## Approach

Decide the template mechanism once (string slots vs a small template engine) and record it in principles.
Theme variants (light/dark text) are part of the pack, chosen by placement.
