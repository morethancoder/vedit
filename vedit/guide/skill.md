---
name: vedit
description: Edit a recording of someone speaking (talk, tutorial, podcast, vlog) into a finished video with the vedit CLI (cut pauses and mistakes, add word-anchored motion graphics and subtitles, render 4K60, cut Reels/Shorts/TikTok/story/feed clips). Use when asked to edit, cut, caption, clip or render a recording, or to pick or build a graphics style. Not for videos with no recorded speech (ads, launch films, music videos, motion graphics, generated explainers): use HyperFrames directly.
---
# vedit

vedit is a CLI. It does the mechanics (transcribe, cut, build, render) and prints short reports. You make the
creative calls by writing small files. vedit never judges the look: you and the user do.

Check the fit first. vedit needs recorded speech: cuts come from the transcript, graphics are anchored to
spoken words and framing follows the speaker's face.

- Use it when a recording of someone speaking (talk, tutorial, podcast, vlog; any video file) must become an
  edited video or short-form clips, or the user wants graphics, subtitles or a new graphics style.
- Do not use it for a video with no recorded speech (ad, launch film, music video, motion graphic, generated
  or faceless explainer, montage): build that in HyperFrames directly and say why vedit was skipped.
- Do not use it for a single ffmpeg job (trim, convert, compress).

## Workflow

Run `vedit guide` once for the map. Then work in the project folder, step by step. Open a guide page only at
the step that needs it. Every report ends with `next:`; `vedit status` shows the stage and running jobs.

1. **Start.** `vedit new <input> --lang ar|en` (other flags: `vedit new --help`), then `vedit transcribe`.
   You write nothing yet. Trouble: `vedit guide ingest`.
2. **Read the talk.** `vedit summarize`, then read `summary.md` (chapters, visual moments, ASR errors) instead
   of the raw transcript. `vedit propose-cuts` drafts `cuts.proposed.yaml`, never final.
   Trouble: `vedit guide drafts`.
3. **Cut.** Open `vedit guide cuts`, then write `cuts.yaml`: judge every proposed cut yourself (risky ones
   first), copy only those you agree with, add your own, name the chapters. Run `vedit cut`, then
   `vedit joins`; fix each flagged join in `cuts.yaml` and cut again until none is left.
4. **Graphics.** Pick the style (`vedit styles`; `vedit guide styles`). Open `vedit guide cues` and one
   `cue-<type>` page per type you use, then write `cues.yaml`: which graphic, on which spoken words, saying
   what. An idea no type covers goes in `custom/` (`vedit guide cue-custom`). Run `vedit build --plan`, then
   `vedit build`.
5. **Review.** `vedit review`, then open every sheet and look (`vedit guide review`). Fix cues, cuts or style
   and build again. Then `vedit draft` opens the draft in QuickTime: hand it to the user. Their notes go back
   into step 3 or 4.
6. **Subtitles.** `vedit subs` once the cut is final; rerun it after any cut change.
7. **Master.** Only after the user approves the draft: `vedit render` (`vedit guide render`).
8. **Upload text.** vedit has no command for it: write titles, description and thumbnail notes in `youtube/`
   (kept by `vedit clean`; YouTube traps in `vedit guide traps`).
9. **Clean up.** `vedit clean` frees caches. Once the video is posted, `vedit clean --posted --dry-run` lists the
   big files with sizes; delete them with `vedit clean --posted` only when the user says so.

## Rules

- Write only `cuts.yaml`, `cues.yaml`, `custom/` and `youtube/`. Never edit `.vedit/`.
- Anchor every cut and cue to spoken words, never to seconds.
- Placement (side, theme, blur) is decided by vedit from the face track. Do not write it.
- Commands marked "(not built yet)" do not exist yet. Say so; do not work around them.
- A long job runs detached. Block on it with `vedit wait --timeout S --json`; never sleep-poll or restart it.
- Open drafts in QuickTime. Never open HyperFrames Studio to review.
- Errors say what to do next. `vedit guide errors` lists the exit codes.

## More

`vedit guide --list` shows every topic. `vedit <command> --help` shows flags and names its guide topic.
