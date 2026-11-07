# vedit wait

Agents must not sleep-poll a detached job.

Done when:
- [x] `vedit wait [--timeout S]` blocks until the running job (render, cut, transcribe) ends; exit 0 on success,
      1 on failure, 124 on timeout (job left running); `--json` prints the final status
- [x] `--events` streams NDJSON progress lines (stage, chunk/piece, frame, eta) while waiting
- [x] no job running: returns the last job's result at once
