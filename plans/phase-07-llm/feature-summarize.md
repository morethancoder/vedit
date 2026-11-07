# vedit summarize

A summary that saves Opus reading the raw transcript cold.

Done when:
- [x] `summary.md`: chapters with source times, visual moments worth a graphic, likely ASR errors, names/terms
- [x] runs on Haiku by default; the fixture summary is reviewed once by Opus for usefulness

## Refs

- prompt: T `work/haiku-prompt.md`, `brief-haiku.md`

## Verified (2026-11-05, fixture vedit-fixture-tele)

Haiku (claude-haiku-5-5), first try: 11.2K in / 13.2K out tokens, $0.009 list price, 52 s. Opus review: useful;
15 chapters (T used 6); starts land within 2 s of 3 of T's 5 chapter holds (51.3, 550.3, 756.3; 231.1 is a
beat inside a chapter, 391.4 is 14 s off),
beats keep the numbers (200K -> 1.7M, 75K views, ~200 users), visual moments match T's brief. Weak spot: ASR
errors leak into beats; "1560 يوم" (T heard 365 days) is still read as a member count, though flagged.
