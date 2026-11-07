# Phase 02: Ingest and transcribe

From a video file (or a recorder project via an importer) to proxies, audio and word-timed transcripts in source time.

Done when:
- [x] `vedit new <video> --lang ar` creates a ready project
- [x] `vedit transcribe` produces words for every source clip, cached

## Children

- [`feature-recorder-reader.md`](feature-recorder-reader.md) — read a recorder project: clean camera, trims, export audio, meta
- [`feature-new.md`](feature-new.md) — `vedit new`: folder, project.yaml, src links, A-cam, proxies, audio
- [`feature-transcribe.md`](feature-transcribe.md) — `vedit transcribe` via Studio
- [`feature-words.md`](feature-words.md) — words model, Arabic normalisation, phrase search, source↔program time

## Refs

- depends on: [`../phase-01-foundation/step.md`](../phase-01-foundation/step.md)
