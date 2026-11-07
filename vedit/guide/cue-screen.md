---
summary: a screen recording over the blurred main footage
next: vedit build
---
# cue type: screen

Status: built; `vedit build` renders it (`vedit build --plan` shows where it lands).

## What it is

A screen recording (demo) shown over the blurred A-roll while you talk about it.

## Write

```yaml
- type: screen
  at: "words that start it"
  near: A 300
  source: B                    # a source id from project.yaml
  from: 12.5                   # seconds into the recording
  kicker: "small line"
  title: "the title"
  steps: ["first", "second"]
```

## Rules

- Fields: `source` (required), `from`, `kicker`, `title`, `steps`. Default length 8 s.
- The recording must be a source in project.yaml (for example `B`); its proxy plays in the window.
- Cut the demo to the part that matters; it covers the speaker.
