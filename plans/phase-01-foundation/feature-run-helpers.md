# Run helpers and reports

Every external call and every command output goes through one small layer.

Done when:
- [x] `run()` time-boxes with `timeout` + `nice`, closes stdin, captures stderr, raises with the last lines on failure
- [x] ffmpeg presets: VideoToolbox decode/encode (h264, hevc, prores), proxy 1080p30, 48 kHz WAV, still frame grab
- [x] reports: text by default, one JSON value with `--json`; step/ok/warn styling ported from T `scripts/_lib.sh`

## Approach

Port `_lib.sh` behaviour (colours, step markers, confirm with `CI=1`/`--yes`) to Python. Logs append to
`.vedit/logs/<command>.log`. A `hash_of(...)` helper for content-hash caching lives here.

## Refs

- `../../docs/traps.md` (stdin, hook on bare ffmpeg)
