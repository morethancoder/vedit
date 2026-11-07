# vedit propose-cuts

A first-draft cut list the model reviews instead of writing from scratch.

Done when:
- [x] writes `cuts.proposed.yaml` in cuts.yaml format, each cut with `why`; never overwrites cuts.yaml
- [x] marks risky cuts (removes numbers, names, negations like "ما", or story content) so review starts there
- [x] on the fixture, compare with T's final cut: report hit rate and risky-cut count

## Refs

- prompt: T `work/sonnet-cuts-prompt.md`

## Verified (2026-11-05, fixture vedit-fixture-tele vs T's real cut work/edl.json)

Sonnet (`claude-sonnet-5-5`), 5 batches of 45 lines: ~18-19K in / ~2K out tokens, ~$0.09-0.12 list price, 23-28 s.
T removed 242 words in 80 runs (fillers included). Two runs:

| run | cuts | runs hit (recall) | word precision vs T | false cuts vs T | risky |
|---|---|---|---|---|---|
| v2 (before join rules) | 64 | 28/80 (35%) | 39% | 37 | 6 (caught 1 of 8 bad) |
| v3 (join rules + join flags) | 59 | 21/80 (26%) | 34% | 38 | 8 (catch 3 of the 4 known-bad that recurred) |

T worked from a different ASR, so "false vs T" overstates it: an Opus review of v2's 37 false cuts found 22
good restarts T could not see, 7 harmless, 8 bad (a name, two meaning flips at the join, torn "الحمد لله",
dangling fragments). Risk flags now also look at the join (negation after the cut, torn phrase, word after
"أنا"). Recall moves ±10 points run to run. 7 of 64 cuts are stutters `vedit words.find` calls ambiguous
(marked `# REPEAT`): an open question for phase 03.
