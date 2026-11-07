# vedit v1

A Python CLI that runs the creator's YouTube edit pipeline with settled defaults, so the model only writes the
creative files (`cuts.yaml`, `cues.yaml`) and picks a style pack.

Done when:
- [ ] the Telegram video (`~/Demos/tele-a7-growth-story`) rebuilds with vedit from its source plus converted
      `cuts.yaml` / `cues.yaml`: same cut, same graphics, 4K60 master renders and verifies
- [ ] the same cues render in both style packs (`yellow-doodle`, `claude-violet`) by changing one line
- [ ] the `youtube-edit` skill drives an edit through vedit commands only, with no scripts to copy
- [ ] any agent learns vedit from `vedit guide` / `vedit skill` alone, with nothing to download
- [ ] a new style is built from reference screenshots through the `vedit style` loop, chosen by the creator, and saved globally (with keywords) or per channel

## Principles

Read and pin [`principles.md`](principles.md) before any node. Background docs: `../docs/` (architecture,
formats, pipeline, studio, models, traps, sources).

## Decisions already made (2026-11-05)

- Python + uv, one package. Extract from the two finished videos (`docs/sources.md`), don't invent.
- All local AI runs in Studio; missing capabilities get added to Studio (phase 06).
- v1 = the edit pipeline + two style packs. Thumbnails and the YouTube upload kit come after v1.
- Rendering stays on HyperFrames/Chrome; no native rewrite. Overlay-only render (graphics alone, transparent,
  only in cue windows, composited by ffmpeg): **not adopted**, because on 192.6 s of the Telegram film it gave
  equal output but was only 1.16× faster (782 vs 910 s): Chrome time fell 62 %, but the ffmpeg composite still
  decodes, composites and re-encodes every 4K frame. Full-frame stays the render path. Revisit if punch-ins move
  into the program pass so frames without graphics can be stream-copied (`phase-04-graphics/spike-results.md`).
- Agent-first is in v1: built-in manual with progressive detail (phase 01), style library with global/channel
  scopes and keywords, and the screenshot → style authoring loop (phase 05). Option review = stills sheet +
  ~10 s clip in QuickTime. Channel set by `vedit new --channel`, saved in project.yaml. The skill is printed by
  `vedit skill`; `vedit skill install` writes only a pointer.

## Children

- [`phase-01-foundation/step.md`](phase-01-foundation/step.md) — package, CLI skeleton, project file, run/Studio helpers, status, built-in guide (others wait on this)
- [`phase-02-ingest/step.md`](phase-02-ingest/step.md) — `new` from a Cap project, proxies, `transcribe` via Studio, words model
- [`phase-03-cut/step.md`](phase-03-cut/step.md) — `cuts.yaml`, listening refine, incremental program, `joins`, `listen`
- [`phase-04-graphics/step.md`](phase-04-graphics/step.md) — `cues.yaml` anchored to words, faces, placement, `build`
- [`phase-05-styles/step.md`](phase-05-styles/step.md) — style pack format, two packs, doodle library, custom cues, style library, style authoring
- [`phase-06-studio/step.md`](phase-06-studio/step.md) [P] — video cut-out in Studio (parallel with phases 02–05; separate repo)
- [`phase-07-llm/step.md`](phase-07-llm/step.md) [P] — model router, prompts, `summarize`, `propose-cuts` (parallel with 03–05, after 02)
- [`phase-08-output/step.md`](phase-08-output/step.md) — `review`, `draft`, `subs`, `render`, `clean`
- [`phase-09-acceptance/step.md`](phase-09-acceptance/step.md) — rebuild the Telegram video, rewrite the skill
- [`phase-10-agentic/step.md`](phase-10-agentic/step.md) — command introspection, error codes, dry run, `vedit wait`
- [`phase-11-formats/step.md`](phase-11-formats/step.md) — clips, shorts, stories, feed posts in every common aspect, clear of platform HUDs

## Decisions (2026-11-07)

- vedit edits every common video shape (phase 11): one recording, many outputs; 16:9 reframed by face track,
  vertical recordings as shot; burned-in animated captions for short-form; safe zones from
  `docs/research/platform-safe-zones.md`, strictest credible source per edge. Thumbnails stay a separate tool.

## After v1 (not planned yet)

Thumbnails (`thumbs.py`, Studio still cut-outs), YouTube upload kit, Jev/kev ranking of proposed cuts,
local text model in Studio.
