# Phase 11: Formats and platforms

vedit edits every common video shape, not only the 16:9 YouTube film: clips cut from a long video, standalone
short videos, stories and feed posts, each kept clear of the platform's on-screen UI.

Decisions (the creator, 2026-11-07):
- Footage: both. 16:9 recordings are reframed with a face-tracked crop; vertical recordings are used as shot.
- One recording, many outputs: a project keeps one cut and transcript and lists outputs (YouTube master,
  clips, story sets, feed posts), each with its own aspect, platforms and graphics layout.
- Short-form captions are burned in, animated word by word, inside the safe zone; YouTube long-form stays SRT.
- v1 types: clips from a long video (9:16), standalone short videos (9:16), stories, feed posts 4:5 and 1:1.
- Thumbnails stay out (a separate tool later).

Done when:
- [x] from the Telegram talk, one project produces the 16:9 master, two 9:16 clips, a story set and a 4:5 post;
      no caption or graphic enters any target platform's HUD (review shows zero `hud` flags)
- [ ] a vertical recording edits end to end as a standalone short
- [x] `vedit guide formats` explains every aspect and platform within the guide budget

## Children

- [`feature-platforms.md`](feature-platforms.md) — aspect + platform registry with HUD safe zones; `vedit formats`; `guide formats`
- [`feature-outputs.md`](feature-outputs.md) — `outputs:` in the project; `vedit output add|list|rm`
- [`feature-reframe.md`](feature-reframe.md) — face-tracked crop of 16:9 to any aspect; vertical sources as shot
- [`feature-layout.md`](feature-layout.md) — graphics compose on any canvas, placed inside the output's safe zone
- [`feature-captions.md`](feature-captions.md) — burned-in animated word captions for short-form
- [`feature-hud-check.md`](feature-hud-check.md) — review flags anything in a HUD; HUD mock on sheets and drafts
- [`feature-stories.md`](feature-stories.md) — split a story output into platform-length segments
- [`feature-render-outputs.md`](feature-render-outputs.md) — draft and render per output

## Refs

- research: `../../docs/research/platform-safe-zones.md` (+ `.json`), 17 placements, sources and confidence
- faces: `vedit/graphics/faces.py`; compose: `vedit/graphics/compose.py`; placement: `vedit/graphics/place.py`

(2026-11-07, `~/Demos/vedit-formats-tele`: master + reel-1, reel-2, story (whole cut), story-bot (127 s, 3 parts),
post 4:5 built; review 0 hud flags on all five. Rendered and checked: reel-1, story-bot. Open: vertical
recordings (box 2) need ingest/proxy, faces and program sizes made aspect-aware; 16:9 doodles and screens read
small as 9:16 cards and want a vertical layout.)
