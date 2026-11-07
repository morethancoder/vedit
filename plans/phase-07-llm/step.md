# Phase 07: Model router and drafting commands

Cheap models draft the summary, the cut list and subtitle text; a weekly limit never blocks the edit.

Done when:
- [x] `vedit llm <prompt>` falls back Haiku → Sonnet → gemma4 cloud with validated JSON output
- [x] `vedit summarize` and `vedit propose-cuts` write their files from the transcript

## Children

- [`feature-router.md`](feature-router.md) — router, prompt files, validation, logging
- [`feature-summarize.md`](feature-summarize.md) [P] — summary.md (parallel with propose-cuts)
- [`feature-propose-cuts.md`](feature-propose-cuts.md) [P] — cuts.proposed.yaml for review

## Refs

- depends on: [`../phase-02-ingest/step.md`](../phase-02-ingest/step.md)
- `../../docs/models.md`
