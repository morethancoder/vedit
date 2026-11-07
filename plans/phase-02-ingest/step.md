# Phase 02: Ingest and transcribe

From a Cap project (or plain files) to proxies, audio and word-timed transcripts in source time.

Done when:
- [x] `vedit new <cap-project> --lang ar --dialect iq --style yellow-doodle` creates a ready project
- [x] `vedit transcribe` produces words for every source clip, cached

## Children

- [`feature-cap-reader.md`](feature-cap-reader.md) — read a `.cap` project: raw camera, trims, export audio, meta
- [`feature-new.md`](feature-new.md) — `vedit new`: folder, project.yaml, src links, A-cam, proxies, audio
- [`feature-transcribe.md`](feature-transcribe.md) — `vedit transcribe` via Studio
- [`feature-words.md`](feature-words.md) — words model, Arabic normalisation, phrase search, source↔program time

## Refs

- depends on: [`../phase-01-foundation/step.md`](../phase-01-foundation/step.md)
