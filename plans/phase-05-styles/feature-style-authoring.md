# Style authoring: from screenshots, by try and judge

An agent builds a new pack from reference screenshots; vedit renders what the agent made so it can compare,
and the creator picks between options.

Done when:
- [x] `vedit style new <name> --from <dir|video>` makes a draft pack (copy of base) under `~/.config/vedit/styles/drafts/<name>/`, copies the refs into `refs/` (a video gets frames sampled at scene changes), extracts the palette (OpenCV k-means) into pack.yaml, and writes `brief.md` for the agent to fill (type, shapes, motion it sees)
- [x] `vedit style try <name>` renders a specimen: every cue type with sample text in the pack's language, as one PNG sheet with the refs beside it, plus `--clip` for a ~10 s 1080p draft MP4 (motion); prints paths and the palette distance to the refs
- [x] `vedit style fork <name> <variant>` makes options; `vedit style compare <a> <b> …` builds one labelled sheet and opens the clips in QuickTime for the creator to choose
- [x] `vedit style pick <name> <variant>` keeps the chosen option and logs the decision (what was picked over what, the creator's reason) in the pack's `history.md`
- [x] `vedit style save <name> --global --keywords "…"` or `--channel <handle>` promotes the draft; `guide style-authoring` written
- [ ] acceptance: from 3–5 screenshots of a channel not yet covered, an agent reaches a saved pack in this loop, and one line in a project switches a video to it

## Approach

vedit never judges the look: the agent (it can see the images) edits tokens and `types/*.html`, vedit renders
and measures. The specimen uses a fixed `specimen.yaml` of sample cues from the base pack, so every pack is
shown with the same content. Font identification is not automated; the agent proposes installed fonts and the
try loop settles it.

## Refs

- depends on: [`feature-pack-format.md`](feature-pack-format.md), [`feature-style-library.md`](feature-style-library.md)
- the specimen is a small HyperFrames project built by the phase 04 engine and rendered directly at draft
  quality; it does not wait for phase 08

## Status (2026-11-05)

Loop proven blind up to `compare`: a fresh agent that never saw claude-violet rebuilt it from 5 frames of C as draft
`tg-blind` (+ option `tg-blind@georgia`); compare sheet with the real pack:
`~/.config/vedit/cache/specimens/compare/tg-blind+tg-blind@georgia+claude-violet.png`. The acceptance box stays open
until the creator supplies screenshots of a new channel, picks, and saves.
