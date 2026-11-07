# Cap project reader

Understand a Cap `.cap` folder well enough to rebuild its edit from the raw camera.

Done when:
- [x] given a `.cap` path, returns raw camera file, export file, timeline segments, fps, `pretty_name`, mirror flag
- [x] matches an export in `~/Movies/YT/<video>/` to its `.cap` via `recording-meta.json` `pretty_name`
- [x] tested on the Telegram video's Cap project (`Built-in Retina Display (Area) 2026-11-03 10.31 AM (1).cap`)

## Approach

Port the segment logic from T `scripts/source.sh` (cumulative export clock → frame counts, no drift).
