# vedit

A CLI that turns the creator's Cap talk recordings into a finished YouTube edit: cleaned-up cut, motion graphics,
subtitles, a 4K60 master. The mechanics are settled in code; the model only makes the creative calls.

**Status:** docs and plan only. Nothing is built yet. Start at [`plans/plan.md`](plans/plan.md).

## Why a CLI and not just a skill

The `youtube-edit` skill used to carry a 4,400-line copy-paste template. Every video copied it and patched it
(9 of 12 scripts changed and 6 added for the Telegram video), so each edit started with the model reading and
re-deciding settled things: crossfade length, pause trimming, render chunking, RTL. vedit keeps those decisions
in code with the best defaults, so one command does one stage and prints a short report.

| Layer | Owns | Decided by |
|---|---|---|
| `vedit` (this repo) | ingest, transcription, applying cuts, join checks, face track, cut-outs, build, render, cleanup | code (settled) |
| `cuts.yaml`, `cues.yaml` (per video) | what to cut, which graphics, what they say, which ideas get a doodle | the model + the creator |
| style packs (built-in, global, per channel) | how every graphic type looks | picked per video/cue, by name or keywords; new ones built from screenshots |
| `vedit guide` / `vedit skill` | how to drive vedit, in small pages | shipped inside vedit, any agent |
| `youtube-edit` skill | the creator's taste rules + "run `vedit guide`" | guides the model |

## A video, start to finish (target)

```
vedit new <cap-project> --lang ar --dialect iq --style yellow-doodle
vedit transcribe                 # Studio, cached
vedit summarize                  # cheap model -> summary.md (chapters, visual moments, ASR errors)
  -> model writes cuts.yaml      #   (vedit propose-cuts drafts one)
vedit cut                        # listens for exact boundaries, renders only changed program pieces
vedit joins                      # prints only the joins that read wrong
  -> model writes cues.yaml      #   graphics anchored to spoken words, not seconds
vedit build                      # cues + style pack -> HyperFrames project, checked
vedit review                     # snapshot sheet at every graphic's peak + automatic flags
vedit draft                      # 1080p draft, opened in QuickTime
vedit subs                       # ar/en SRT
vedit render                     # 4K60 master, chunked, resumable
vedit status                     # stage, stale outputs, running render progress
vedit clean [--posted]           # caches; --posted also deletes the originals (asks first)

vedit guide [topic]              # built-in manual: one-screen map, detail per topic on demand
vedit skill [install]            # agent skill (printed; install writes a pointer only)
vedit styles [find "<words>"]    # global, channel and built-in packs
vedit style new|try|fork|compare|pick|save   # build a style from screenshots, the creator picks options
```

## Rules that shape it

- **All local AI runs in Studio** (`studio` CLI, `~/Projects/New/studio`): transcription, cut-outs, judgments.
  If vedit needs a better model, it gets added to Studio, never bundled into vedit. See [`docs/studio.md`](docs/studio.md).
- Cloud language models (Haiku, Sonnet, gemma via Ollama cloud) go through one router with saved prompts.
- Python + uv. Every ffmpeg job on VideoToolbox, time-boxed.

## Docs

| File | What |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | layers, project folder layout, data flow, commands |
| [`docs/formats.md`](docs/formats.md) | `project.yaml`, `cuts.yaml`, `cues.yaml`, style pack format |
| [`docs/pipeline.md`](docs/pipeline.md) | what each stage must do, with the settled numbers (moved from the skill) |
| [`docs/studio.md`](docs/studio.md) | what Studio already does for vedit, and what must be added to it |
| [`docs/models.md`](docs/models.md) | which model does which job, and the router |
| [`docs/traps.md`](docs/traps.md) | mistakes already made once (moved from the skill) |
| [`docs/sources.md`](docs/sources.md) | the two finished videos vedit is extracted from, file by file |
| `reference/` | the old skill text and its English template, kept as extraction source |
