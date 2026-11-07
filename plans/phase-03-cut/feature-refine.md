# Refine by listening

Pick the cleanest real boundary for every phrase/filler cut.

Done when:
- [x] for each cut: K=3 quiet points per side, 9 splices with 1.6 s context, all in one WAV, one Studio pass
- [x] the winning splice reads "before + after" without the removed words; ties go to the quietest join
- [x] cached per cut; only new or edited cuts are listened to

## Refs

- port T `tools/refine.py` (already on Studio)
