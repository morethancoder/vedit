---
summary: one-screen map of vedit
next: vedit status
---
# vedit

vedit turns a talk recording (any video file) into a finished YouTube edit: cleaned-up cut, motion
graphics, subtitles, a 4K60 master. Code owns the mechanics. You own the creative calls, written as data.

## The edit loop

Run these inside the project folder, in order. `vedit status` tells you where you are.

{{loop}}

Every command prints a short report ending in `next:`. Add `--json` for one JSON value. Re-running a command
is safe: it redoes only what changed.

## Files you write

- `cuts.yaml`: what to remove, chapters, pins. Words, not seconds.
- `cues.yaml`: graphics, each anchored to spoken words so they survive any cut change.
- `custom/`: one-off HTML/GSAP graphics that a `custom` cue points to.
- `project.yaml`: language, sources, style. Written by `vedit new`; edit only to change style or hints.

Never edit `.vedit/`: it is generated and `vedit clean` may delete it. Edits to generated files are overwritten.

## Go deeper

- Before writing `cuts.yaml` run `vedit guide cuts`; before `cues.yaml` run `vedit guide cues`, then the
  page for each cue type you use (`vedit guide cue-label`, ...).
- A command fails or says "not built yet": `vedit guide errors`.
- Reels, Shorts, TikToks, stories, feed posts from the same edit; platform safe zones: `vedit guide formats`.
- Driving vedit from an agent (command data, error codes, `--dry-run`, `vedit wait`): `vedit guide agents`.
- Flags for one command: `vedit <command> --help`. Agent skill text: `vedit skill`.
- All topics with one line each: `vedit guide --list`.

Topics: {{topics}}
