---
summary: chapter card, generated from cuts.yaml
next: vedit build
---
# cue type: chapter

Status: built; `vedit build` renders it (`vedit build --plan` shows where it lands).

## What it is

A short silent hold with a chapter title. You do not write it.

## How to get one

Add an entry under `chapters:` in `cuts.yaml` (`vedit guide cuts`). vedit generates the `chapter` cue from it,
with a 1.8 s silent hold.

## Rules

- Fields (from cuts.yaml `chapters:`): `title` (required), `kicker`, `logo`. It runs from 0.5 s before its hold to 0.9 s after.
- Do not write `type: chapter` in cues.yaml.
- Change a chapter by editing its `title` or `near` in cuts.yaml.
