# Phase 03: The cut

Apply `cuts.yaml` with listening-verified boundaries, render the program incrementally, report bad joins.

Done when:
- [x] `vedit cut` turns cuts.yaml into an edl and a 1080p program; changing one cut re-renders only its pieces
- [ ] `vedit joins` prints only joins whose words don't read right

## Children

- [`feature-cuts-file.md`](feature-cuts-file.md) — cuts.yaml loader: phrases, from/to, pins, fillers, pauses, chapters, end
- [`feature-refine.md`](feature-refine.md) — find real boundaries by listening (Studio)
- [`feature-edl.md`](feature-edl.md) — edl from cuts: snapping, 1/30 s grid, holds, end fade, punch-ins
- [`feature-program.md`](feature-program.md) — program render per piece + concat, crossfaded audio
- [`feature-joins.md`](feature-joins.md) [P] — transcribe program, expected-vs-heard report (parallel with listen)
- [`feature-listen.md`](feature-listen.md) [P] — `vedit listen` for ad-hoc probes (parallel with joins)

## Refs

- depends on: [`../phase-02-ingest/step.md`](../phase-02-ingest/step.md)
- `../../docs/pipeline.md` (cut, joins sections)
