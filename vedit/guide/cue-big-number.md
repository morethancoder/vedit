---
summary: a big word or number behind the head, person cut out over it
next: vedit build
---
# cue type: big-number

Status: built; `vedit build` renders it (`vedit build --plan` shows where it lands).

## What it is

One large word or figure placed behind the speaker, with the person cut out in front of it.

## Write

```yaml
- type: big-number
  at: "words that start it"
  near: A 12
  pre: "text shown before the number"
  word: "1.7M"
```

## Rules

- Fields: `word` (required), `pre`, `color`. Default length 5 s.
- `color: accent` uses the style's accent (any pack colour name works), so a style switch needs no cue edit.
- It needs a clean cut-out of the person; vedit builds that, you do not.
