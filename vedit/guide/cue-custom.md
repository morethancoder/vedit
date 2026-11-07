---
summary: escape hatch: any HTML/GSAP sub-composition
next: vedit build
---
# cue type: custom

Status: built; `vedit build` renders it (`vedit build --plan` shows where it lands).

## What it is

Your own graphic as one HTML file with GSAP motion, for what no built-in type covers.

## Write

```yaml
- type: custom
  at: "words that start it"
  file: custom/intro.html
  for: 4.0
  box: [100, 620, 700, 320]   # optional: where it draws, x y w h in 1920x1080 px
```

## Rules

- Fields: `file` (required, must exist), `for` (required: no default length), `box` (optional, x y w h px),
  `face` (`ignore` to skip the face check).
- Face check: the graphic is checked against the face track over its `box`; without one it counts as the full
  frame and `vedit build` warns. Give a `box` that keeps clear of the face, or `face: ignore` for a full-frame
  look that is meant to sit behind or over him.
- Put the file under `custom/` in the project. It is the one place besides cues.yaml and cuts.yaml you write.
- One file is one sub-composition (`<template>`, a `data-composition-id` root, one timeline); vedit sets its
  id to the cue id. Paths inside start at the HyperFrames project: write `custom/...` for your files.
- Give every audio element a duration and guard tweens of optional elements.
- Do not use backdrop blur inside any parent with opacity below 1.
- Try a built-in type first. Custom HTML is not restyled by itself, but it can read the pack through variables.

## Style variables

vedit puts the pack's tokens on the graphic's root, with the pack's fonts loaded, so a style switch restyles it:

- one variable per pack colour, named vedit-accent, vedit-ivory... with two leading dashes; accent follows the channel
- text, sub, kicker, shadow from the pack's dark theme (vedit-text...)
- vedit-font-text, vedit-font-mono, vedit-font-hand (and any other `font` key)

```html
<template>
  <style>
    #root .card { color: var(--vedit-text); font-family: var(--vedit-font-text);
      border-bottom: 6px solid var(--vedit-accent); text-shadow: var(--vedit-shadow); }
  </style>
  <div id="root" data-composition-id="intro" data-width="1920" data-height="1080">
    <div class="card">Hello</div>
  </div>
  <script>
    const tl = gsap.timeline({ paused: true });
    tl.from(".card", { opacity: 0, y: 30, duration: 0.5 }, 0);
    window.__timelines["intro"] = tl;
  </script>
</template>
```
