# Compose the HyperFrames project

Assemble program, cut-outs and graphics into one composition.

Done when:
- [x] `index.html` + one sub-composition per graphic, tracks, punch-in zooms, chapter cards, end fade over running footage
- [x] SFX placed per the pack's map, ~18 dB under the voice, every `<audio>` with `data-duration`
- [x] `vedit build` runs `hyperframes lint` + `check`; only changed cues regenerate (by cue hash)
- [ ] ~~overlay mode~~ not adopted (spike): full-frame only; hosts are grouped `behind`/`front` so it can slot in later. Was: overlay mode (if the spike adopts it): two transparent layers (`behind` = under the cut-out, `front`), a
      window list of where each has graphics, and a composite plan (zooms, blur regions, fades, layer order)
      in `.vedit/composite.json` for ffmpeg; full-frame mode stays available as `--full` for comparison

## Overlay mode

The A-roll never goes through Chrome. Anything that touches the footage itself (punch-in zoom, blur behind a
screen cue, end fade, chapter card background) is a composite step, not HTML. See
[`feature-overlay-spike.md`](feature-overlay-spike.md).

## Refs

- port T `tools/build.py` `host`, `index`, `page`, SFX tables
- `../../docs/traps.md` (HyperFrames section)

## Verified (2026-11-05, fixture `~/Demos/vedit-fixture-tele`)

48 graphics (5 chapters), 98 sounds, 67 punch-ins, 16 blur windows, 6 render chunks (`.vedit/hf/chunks.json`).
`hyperframes check` passes: 9 layout samples, contrast 6/6, 0 errors. Warm rebuild writes nothing; changing one
cue's title rewrites only that composition. Snapshot sheets `.vedit/build/sheet-{1,2}.jpg` and side by side with
T's render `.vedit/build/sheet-vs-T-{1,2}.jpg`: same layout as T. Doodles are a placeholder until phase 05.
