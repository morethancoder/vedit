---
summary: a small tag shown with a spoken word
next: vedit build
---
# cue type: chip

Status: built; `vedit build` renders it (`vedit build --plan` shows where it lands).

## What it is

A small chip of text near the speaker for a term, name or number. Fields beyond `at` and `near` are not
fixed yet; they are written when the type is built (phase 04).

## Write

```yaml
- type: chip
  at: "words that start it"
  near: A 40
  label: "small line above the code"
  code: "text typed out"
```

## Rules

- Fields: `label` and `code` (both required), `logo`. Default length 8 s.
- Use `label` when you need a logo or a title with a kicker.
