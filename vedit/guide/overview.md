---
summary: one-screen map of vedit
next: vedit status
---
# vedit

vedit turns a recording of someone speaking (any video file) into a finished edit: cleaned-up cut, motion
graphics, subtitles, a 4K60 master, plus short clips for Reels, Shorts, TikTok, stories and feed posts.
Code owns the mechanics. You own the creative calls, written as data.

## Is vedit the right tool

- Fits: a talk, tutorial, podcast or vlog recording (Arabic or English) that needs a cut, graphics,
  subtitles or short-form clips. Best with the speaker on camera.
- Does not fit: a video with no recorded speech (ad, launch film, music video, motion graphic, generated or
  faceless explainer, montage). Build those in HyperFrames directly.
- Does not fit: a single ffmpeg job (trim, convert, compress).
- Why: cuts come from the transcript, graphics are anchored to spoken words, framing follows the face.

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
