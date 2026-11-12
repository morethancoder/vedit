# Vertical recordings

A recording shot vertical (a phone, a 9:16 screen capture) edits end to end as a standalone short, used as shot.
Closes phase 11's open box "a vertical recording edits end to end as a standalone short" and feature-reframe's
"a source already in the target aspect passes through untouched".

## What is landscape-only today (sweep 2026-11-07)

- ingest: `run.proxy_1080p30` scales every source to 1920x1080, so a vertical source is stretched. Phone files
  often store landscape pixels plus a rotation tag, so the real shape must come from ffprobe's rotation too.
- faces: `faces.py` detects at 960x540 and doubles boxes to 1920x1080; the check sheet draws on 1920x1080.
- program: `cut/program.py` PROFILES fix the proxy at 1920x1080 and the master at 3840x2160.
- main composition: `graphics/compose.py` and `pages.py` write a 1920x1080 root; `render/master.py` and
  `render/hf.py` render 4K 16:9.
- outputs: `formats/reframe.py` crops width only (SRC_W, SRC_H = 1920, 1080); `formats/layout.py` and
  `compose_out.py` place 1920x1080 scenes as cards; `project.default_outputs()` gives a 16:9 master.
- about 30 files hold a 1920/1080/3840/2160 literal (doodles, specimens and review sheets included).

## Acceptance criteria (approved 2026-11-07)

1. `vedit new` on a vertical file (9:16, or landscape pixels with a 90/270 rotation tag) makes a 1080x1920 30 fps
   proxy, a contact sheet with tall tiles and, for camera sources, a vertical A-cam. Nothing is stretched.
   project.yaml records `canvas: 9:16`, taken from source A.
2. Faces are tracked on the vertical proxy. Boxes are in that proxy's pixels, and punch-ins centre on the face.
3. `vedit cut` renders a 1080x1920 program proxy and a 1080x1920 60 fps master; joins, listen and subs work
   unchanged.
4. A vertical project's default output is one 9:16 short (Reels, Shorts, TikTok). A 4:5 or 1:1 output is a
   face-tracked crop of the height. A 16:9 output of a vertical source sits on the canvas fill (criterion 9).
5. `vedit build` places every cue type on the 9:16 canvas inside the safe zone, using the phase-11 layout:
   overlays in the safe box, full-frame scenes as cards, and burned captions that dodge the HUD.
6. `vedit review` flags work, and none enters a HUD. `vedit draft` and `vedit render` give 1080x1920 files.
7. Landscape projects are untouched: same media hashes on the acceptance copy, and the full suite passes.
8. Evidence: two or three 9:16 reels made from a face-tracked 9:16 crop of the Telegram talk (the vertical source,
   made once with ffmpeg and kept beside the acceptance copies). Each reel follows the viral recipe in the "Viral
   vs Selling Reels" research (claude.ai artifact LLf9oWCCpHULtZoB7kb7En):
   - a hook card with on-screen text in frame 1 that works muted
   - one idea, 20–35 s
   - a pattern, then one break
   - an ending line that loops back to frame 1
   - the same look across the series
   Doodle-art cues carry the idea. Each reel runs through new, transcribe, cut, joins, build, review, draft and
   render. I look at the drafts, review sheets and HUD mocks, and the report gives counts and timings.
9. Shapes that don't fill the canvas (a mixed-shape source, a vertical source in a 16:9 output) sit on a fill:
   `plain` by default (a solid colour from the style), `blur` only when asked, or `shader` (an animated shader
   background). The fill is a per-project or per-output setting (CLAUDE.md: no blur by default).

## Decisions (2026-11-07)

- Criteria approved as written; master 1080x1920 60 fps.
- Test footage: a 9:16 crop of the talk plus doodle graphics, made to the viral-reels recipe.
- Mixed shapes: fitted on a fill. The default is plain, never blur. Blur and shader are options.
