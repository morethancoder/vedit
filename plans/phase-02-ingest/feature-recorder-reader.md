# Recorder project reader

Understand a recorder project well enough to rebuild its edit from the clean camera.

Superseded 2026-11-07: recorder readers are importer plugins outside the repo
([`../phase-12-agnostic/feature-importers.md`](../phase-12-agnostic/feature-importers.md)); the generic part
(clean camera on trims) is `vedit/recording.py`.

Done when:
- [x] given a recorder project path, returns clean camera file(s), export file, trims, fps, name, mirror flag
- [x] matches an export file back to its recorder project
- [x] tested on the Telegram video's recorder project

## Approach

Port the segment logic from T `scripts/source.sh` (cumulative export clock → frame counts, no drift).
