# Rebuild the Telegram video

The acceptance test for v1.

Done when:
- [x] on a copy: `new` → `transcribe` → `cut` → `joins` → `build` → `review` → `draft` → `subs` → `render` with the converted cuts.yaml / cues.yaml
- [ ] cut length 13:08 ± 1 s, same graphics count, joins report clean, review flags none that T didn't have
- [x] the same cues build in `claude-violet` by changing one line; record time and tokens of the run in `docs/models.md`

(open box 2: cut 13:08.70 ok, 48 graphics ok, review 2 flags same as T ok, but joins flag 26 of 160; a few look
real (missing words at 409.3, 413.8, 733.1; اذا doubled at 778.4) and need the creator's ear before pins in cuts.yaml.)
