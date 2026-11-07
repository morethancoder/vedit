# vedit subs

YouTube captions in Arabic and English from the final cut.

Done when:
- [x] cues from the program transcription (≤ 84 chars, ≤ 6 s, split on 0.6 s gaps)
- [x] cleanup + translation through the router in batches of 40, ids round-trip
- [x] `subs/ar.srt` (U+200F per line, U+200E before symbol-led tokens) and `subs/en.srt`, `en.txt`

## Refs

- port T `tools/subs.py`, `subs_llm.py`; prompt T `work/sonnet-subs-prompt.md`
