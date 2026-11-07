---
summary: write cues.yaml: graphics anchored to spoken words
next: vedit build
---
# cues.yaml

Status: built. `vedit build` places every cue, writes the HyperFrames project and checks it.

## Shape

```yaml
style: base                       # default style for every cue; a cue may override with style:
cues:
  - type: label
    at: "words that start it"     # the phrase to find, spoken
    near: A 92                    # source clip + approximate time
    ...type fields...
```

## Rules

- Every cue is anchored to spoken words (`at`), so it survives any cut change.
- End a cue with `until: "words"` (the first time they are spoken after `at`, within 90 s), `until: end` (the
  program end) or `for: <seconds>`. With none, the type decides: label 6 s, chip 8, big-number 5, screen 8,
  plug 18; kinetic ends 1.2 s after its last word, doodle 2.5 s after its last beat; custom needs `for`.
- `near` is optional only when `at` is spoken exactly once in the whole project.
- Style: a cue's `style:`, else the file's `style:`, else project.yaml `style`, else `base`.
- A cue whose `at` words were cut away is kept and reported, never dropped.
- Unknown fields, bad logos and missing required fields are all reported together.
- vedit snaps the window inside one continuous shot.
- Never write placement (side, theme, blur): vedit decides it from the face track and frame brightness.
- A new look is a style pack, not a change to cues: `vedit guide styles`.

## Types in v1

Read the page for each type you use before writing it.

- `label`: `vedit guide cue-label`
- `chip`: `vedit guide cue-chip`
- `kinetic`: `vedit guide cue-kinetic`
- `big-number`: `vedit guide cue-big-number`
- `doodle`: `vedit guide cue-doodle`
- `screen`: `vedit guide cue-screen`
- `chapter`: `vedit guide cue-chapter` (generated from cuts.yaml; you do not write it)
- `plug`: `vedit guide cue-plug`
- `custom`: `vedit guide cue-custom`

## Face track

`vedit faces` samples the face at 4/s (cached); `vedit faces --sheet` draws boxes on a contact sheet to check
by eye. `vedit build` runs it by itself; run it alone to look at the sheet.

## After writing

- `vedit build --plan`: where each cue lands (window, side, theme), fitted windows and problems; writes nothing.
- `vedit build`: writes `.vedit/hf/` (one composition per cue, `index.html`, sounds, zooms, blur, end fade),
  cuts the person out for big words, then runs `hyperframes lint` + `check`. Only changed cues are rewritten.
  `--no-check` skips the checks for a fast loop. Edits made inside `.vedit/hf/` are overwritten.
- Then `vedit review` (see `vedit guide review`).
