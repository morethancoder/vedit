# Sources: where each feature already exists

Two finished videos. Lift from them; don't rewrite from memory.

- **T** = `~/Demos/tele-a7-growth-story/` (Arabic Iraqi, one Cap camera clip, yellow `#FFD60A`, Studio
  transcription, 2026-11). The newer, language-aware one: prefer it.
- **C** = `~/Demos/claude-in-telegram-video/` (English, three Cap clips + screen recordings, violet Claude look,
  whisper.cpp, 2026-10). Its tools snapshot is also in `reference/template-claude-in-telegram/`.

| vedit module | Source | Notes |
|---|---|---|
| `ingest/cap.py` | T `scripts/source.sh` | raw camera on Cap trims, frame-exact |
| `ingest/media.py` | T `scripts/media.sh`, `source.sh` | proxies, 48k WAV, program/matte symlinks |
| `words/` | T `tools/words.py`, `build.py` (`wnorm`, `_AR` table) | Arabic normalisation lives in build.py today |
| `words/` time mapping | T `tools/timeline.py` | `g(clip, t)` source→program, `src(t)` back |
| `cut/` phrases, fillers, pauses, snapping | T `tools/cuts.py` | `PHRASES`/`OVERRIDES` become cuts.yaml |
| `cut/refine.py` | T `tools/refine.py` | already on Studio |
| `vedit listen` | T `tools/probe.py`, `pprobe.py`, `stamps.py` | three tiny scripts → one command |
| `cut/program.py` | T `tools/program.py` | add per-piece incremental render |
| `cut/joins.py` | T `tools/joins.py` | add expected-vs-heard diff |
| `graphics/faces` | T `tools/faces.py` | |
| `graphics/` placement | T `tools/build.py` (`face_at`, `hits_face`, `side_for`, `lum`, `theme_for`, fit-in-shot, `zoom_plan`) | |
| `graphics/` hosts + index | T `tools/build.py` (`host`, `index`, `page`, SFX) | |
| types label, chip, kinetic, big, chapter, plug | T `tools/build.py` (`label`, `chip`, `kinetic`, `big_layout`/`big`, `chapter`, `ptb`) | become yellow-doodle `types/*.html` |
| type screen | C `tools/build.py` (screen-recording scenes), T `broll1`/`broll2` | |
| violet types | C `tools/build.py` + `design.md` | become claude-violet pack |
| big-word text metrics | T `tools/plex700-advances.json`, C `serif600-advances.json` | per-font advance tables, per pack |
| `doodles/` primitives | T `tools/doodles.py` (1,111 lines) | seeded wobble, strokes, icons |
| doodle scenes | T `tools/doodles_tele.py` (12), C `tools/doodles.py` scenes | become the scene library |
| cut-outs (fallback only) | T `scripts/matte.sh`, `tools/matte_mask.py` | `studio cutout` on video is the method; this is the old-Studio fallback |
| `render/` | T `scripts/render.sh` | chunks, resume, join, verify |
| `subs/` | T `tools/subs.py`, `tools/subs_llm.py` | |
| prompts | T `work/haiku-prompt.md`, `brief-haiku.md`, `sonnet-cuts-prompt.md`, `sonnet-joins-prompt.md`, `sonnet-subs-prompt.md`, `sonnet-doodles-task.md` | → `prompts/*.md` |
| `clean.py` | T/C `scripts/clean.sh` + skill step 11 (docs/pipeline.md) | |
| `doctor` | T `scripts/doctor.sh` | |
| run helpers, logging | T `scripts/_lib.sh` | colours, `step`/`ok`, confirm, port guard |
| thumbnails (later) | C/T `tools/thumbs.py`, `still_mask.py` | layout + LIFT/glow details: `reference/youtube-edit-skill-before-vedit.md` step 10 |
| upload kit (later) | T `youtube/` | captions, chapters, description, titles |

## Acceptance fixture

The Telegram video is the test: rebuilding it with vedit from its source and a `cuts.yaml` + `cues.yaml`
converted from T's `cuts.py` / `build.py` should give the same 13:08 cut with the same graphics.
