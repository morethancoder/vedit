# Architecture

## Package

Python ≥ 3.12, one package `vedit`, installed with `uv tool install -e .` so `vedit` is on PATH. Heavy optional
deps (numpy, soundfile, opencv-python-headless pinned `4.10.0.84` with `numpy<2`) live in the package's own
dependencies; no `uv run --with …` one-offs. HyperFrames is called as `npx --yes hyperframes@<pinned>`.

```
vedit/
  cli.py            command table, --json on every command, exit codes
  project.py        find + load project.yaml, paths, stage state
  run.py            subprocess helpers: timeout + nice, ffmpeg VideoToolbox presets, no stdin (</dev/null)
  studio.py         thin client over `studio --json …` (transcribe, cutout, judge), job waiting, caching
  llm.py            model router + prompt files (prompts/*.md)
  ingest/           media.py (A-cam from a clean camera on its trims, proxies, audio)
  recording.py      Recording/Camera/Trim: what importer plugins return
  importers.py      loads importer plugins from <config>/importers/
  words/            transcript model, Arabic normalisation, source<->program time
  cut/              cuts.yaml loader, refine (listening), edl, program render (incremental), joins report
  graphics/         cues loader, anchors, placement (faces, side, theme, fit-in-shot), hosts, index.html
  styles/           built-in packs: yellow-doodle/, claude-violet/   (+ ~/.config/vedit/styles/ for user packs)
  doodles/          primitive library + scene spec renderer
  review/           snapshots, contact sheets, automatic flags
  render/           draft, 4K chunked render, join, verify, detached status
  subs/             cues from program words, translate via llm, SRT writer
  clean.py
  guide/            built-in manual: overview.md, skill.md, one <topic>.md per area/cue type (line-budgeted)
  stylekit/         style new/try/fork/compare/pick/save, palette extraction, specimen
prompts/            summary.md, propose-cuts.md, join-check.md, subs.md
```

## A video project (created by `vedit new`)

```
~/Demos/<slug>/
  project.yaml      language, dialect, style, sources, accent overrides, pinned versions
  src/              links to the originals (edited video, clean camera tracks, screen recordings)
  summary.md        cheap-model summary of the transcript
  cuts.yaml         the cut (creative, model-edited)
  cues.yaml         the graphics (creative, model-edited)
  custom/           one-off HTML/GSAP graphics referenced by `type: custom` cues
  youtube/          upload kit (later phase)
  .vedit/           everything generated: transcripts, edl, program, proxies, cut-outs, hf/, renders, logs
```

The split is the point: **the model edits only `cuts.yaml`, `cues.yaml` and `custom/`**. Everything under `.vedit/`
is reproducible from those plus `src/`, so `vedit clean` can delete it freely.

## Data flow

```
src/ --new--> A-cam + proxies + 48k audio
     --transcribe (Studio)--> words (source time)
cuts.yaml + words --cut--> refined boundaries --> edl --> program (proxy | 4K)
program audio --joins (Studio)--> program words --> bad-join report, subtitle cues
cues.yaml + words + edl + faces + style pack --build--> .vedit/hf/ (HyperFrames project)
hf/ --review--> snapshot sheets + flags      hf/ --draft--> 1080p MP4 in QuickTime
hf/ --render--> 4K60 chunks --> master MP4

overlay mode (planned): hf/ --Chrome, graphics windows only--> behind.mov + front.mov (alpha)
  program + composite.json + cut-outs + behind/front --ffmpeg VideoToolbox--> draft | 4K60 master
```

## Incremental by content hash, never by file date

Every derived artefact records the hash of what it was made from (an edl piece, a cue, a cut-out range + cut).
`vedit cut` re-renders only program pieces whose source range changed; `vedit build` regenerates only the cues
that changed; cut-outs rebuild only when their range or the cut changes. Re-encoding a file must never trigger
a 30-minute 4K background removal.

## Output contract

- Every command prints a short human report by default and exactly one JSON value with `--json`.
- Reports list only problems and decisions to make (e.g. `joins` prints the 4 bad joins, not all 152).
- Long jobs (4K render, cut-outs) run detached, log to `.vedit/logs/<cmd>.log`, write progress to
  `.vedit/state.json`; `vedit status` reads it. A session that stops polling never loses a running render.
- Destructive commands (`clean --posted`) list what they'll delete with sizes and ask; `--yes` skips the ask.
