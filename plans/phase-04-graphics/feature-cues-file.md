# cues.yaml

Load the graphics file and resolve every cue to a program-time window.

Done when:
- [x] every type in docs/formats.md validates against the pack's declared slots; unknown slots are errors
- [x] `at` + `near` resolve via the words model; `until` / `for` set the end; doodle `beats` resolve per element
- [x] T `tools/build.py` `CUES` + `CHAPTERS` convert into a cues.yaml for the fixture (script in `scripts/convert/`)

## Approach

Cues are anchored to words in source time, then mapped through the edl, so a cut change never needs re-timing.
A cue whose words were cut away is reported, not dropped.
