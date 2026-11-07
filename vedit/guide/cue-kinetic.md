---
summary: word-synced spoken text on screen
next: vedit build
---
# cue type: kinetic

Status: built; `vedit build` renders it (`vedit build --plan` shows where it lands).

## What it is

The spoken line shown as text, each word appearing as it is said, with chosen words highlighted.

## Write

```yaml
- type: kinetic
  at: "words that start it"
  words: "the text as shown"
  highlight: ["last words"]    # parts to emphasise
```

## Rules

- Fields: `words` (required), `highlight` (list), `center` (bool).
- No `until`/`for`: it ends 1.2 s after the last shown word is spoken.
- `words` follows the spoken words; the engine times each word from the transcript.
