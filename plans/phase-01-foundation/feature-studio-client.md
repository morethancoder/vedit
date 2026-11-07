# Studio client

`vedit/studio.py`: the only door to local AI.

Done when:
- [x] `transcribe(path, lang, dialect, hint, fillers, vad)` returns words with times; results cached by input hash + options under `.vedit/studio/`
- [x] `cutout_image(path)` and `judge(...)` wrappers exist; Studio stderr warnings come back in the report
- [x] a clear error when Studio is unreachable or a model isn't downloaded, naming the fix

## Approach

Shell out to `studio --json …` (it starts its server on demand). Parse the transcript JSON shape used in
T `tools/joins.py` (`transcript.segments[].words[] {start,end,text}`). Keep it thin; no retries beyond one.

## Refs

- `../../docs/studio.md`
