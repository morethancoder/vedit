# vedit transcribe

Word-timed transcripts of every source clip through Studio.

Done when:
- [x] Arabic uses qwen3-asr-1.7b with `--dialect` and `--hint` from project.yaml, fillers kept; English uses Studio's English model
- [x] writes `.vedit/words/<clip>.json` `[{t0,t1,w}]` and a readable `<clip>.txt` with times every line
- [x] second run is instant (cache hit)

## Refs

- depends on: [`../phase-01-foundation/feature-studio-client.md`](../phase-01-foundation/feature-studio-client.md)
