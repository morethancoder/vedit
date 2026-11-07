---
summary: a lower-third card: logo, kicker line and title
next: vedit build
---
# cue type: label

Status: built; `vedit build` renders it (`vedit build --plan` shows where it lands).

## What it is

A card that names a thing while it is spoken: a logo, a small kicker line and a title.

## Write

```yaml
- type: label
  at: "words that start it"
  near: A 92
  logo: telegram           # a logo the style pack (or your config logos/) offers
  kicker: "small line above"
  title: "the title"
```

## Rules

- Fields: `logo`, `kicker`, `title` (required), `sub`, `mono` (bool). Default length 6 s.
- `logo` must exist in the style pack (`logos/`); see `vedit guide styles`.
- End it with `until` or `for`; placement is decided by vedit.
