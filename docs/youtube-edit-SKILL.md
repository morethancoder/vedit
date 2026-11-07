---
name: youtube-edit
description: >
  the creator's (morethancoder) YouTube edit taste: turn his Cap talk recordings (+ screen recordings, product demos) into
  one cleaned-up, motion-designed video with Arabic + English SRT subtitles, then a 4K60 render on approval, using the
  `vedit` CLI. Use whenever the creator says "edit this video for YouTube", "make the YouTube edit", "cut this talk", "add
  motion graphics / doodles / captions to my video", drops Cap exports or screen recordings in a folder, or asks to
  change/redo a video made this way. It holds his taste; vedit holds the mechanics.
---

# the creator's YouTube edit

**How:** run `vedit skill` for the workflow, then `vedit guide` for the map, and `vedit guide <topic>` at the
step that needs it. Don't re-decide what vedit already decides.

**This file is his taste.** He wants all of it, every time; don't ask again. The creative calls are yours: what
to cut, which graphics and doodles, every on-screen line, the chapter titles,
the upload kit.

## Deliverable

- A draft for his review first; the 4K60 master only after he approves it.
- Arabic + English SRT for YouTube. **No burned-in captions.**
- End a finished round with one line: "once it's posted, tell me and I'll delete the big files (~N GB)".

## The cut

- Start on the first real sentence (cut "So"-style openers); that line as big centred kinetic text.
- Cleanup cuts, especially in intro and setup: fillers, false starts, repeats, rambling asides, over-used tics
  (keep a few where the sentence needs them). **Keep his jokes and personality.**
- Tight pauses; silence only at chapter breaks, under a chapter card, with no sound effect.
- A natural repeat beats a broken word: if a join clips or changes meaning, drop or pin the cut.
- Fade to black on the last word over running footage, never a freeze frame.

## Graphics

- **Never on his face**, in any pose. **No backgrounds behind text** (no cards, glows, pills, boxes); contrast from
  text shadows, and a backdrop blur over busy screens.
- Text on the A-roll leaves before the shot changes.
- Mix logos by topic: Claude spark, Telegram plane, his morethancoder octopus.
- Labels at his hands when he points, only if they can't touch his face.
- Big words behind his head: at most one letter tucked behind it, bookshelf not in the cut-out.
- Kinetic word-synced text at punchlines.
- Doodle explainers for every explanation: drawn on the words, finished ~2.5 s after the last element, never an
  empty blurred frame, never static while he keeps talking.
- Screen recordings: full frame over the blurred A-roll, sped up to fit their line, irrelevant parts cut.
- Product plug (PowerTeleBot): phone demo + the URL as plain text that a cursor clicks, never before he names it.
  Check his claims against the site (it's a 3-day free trial; MCP connection is free for now).
- Sound effects calm and subtle (soft click, pop, short whoosh, key press). No sparkles or bells.
- Looks so far: `claude-violet` (Claude Code in Telegram, English) and `yellow-doodle` (Telegram growth story,
  Arabic, hand lettering). A new look is a new style, not a change to the cues.

## Upload kit

- Description: **important URLs first** (his product plug, then main tool/docs links, "Name: URL" one per line),
  a 2-line hook with the search words, "In this video" bullets, quick-setup commands, more resources (every link
  checked live), chapters, his links, 3 hashtags.
- Five titles, search words first, ≤ 70 chars; chapters from the chapter cards.
- Thumbnails: his cut-out + the video's design language, headline ≤ 4 words, each saying something its title
  doesn't; pair every title with a thumbnail and recommend one pair, others for Test & Compare.
  **His eyes clearly open** (pick from 4K eye-band crops, not proxy sheets). Favourite layout: cut-out left, a
  doodle row top right (icon → arrow → icon), serif headline below. Also offer a real-background version with the
  room lifted toward the video's accent colour.
