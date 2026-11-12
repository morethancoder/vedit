---
summary: driving vedit from an agent: command data, error codes, dry runs, waiting on jobs
next: vedit commands --json
---
# Driving vedit from an agent

vedit is built to run with no human watching. Five rules:

1. **Read the surface as data.** `vedit commands --json` lists every command with its flags (type, default,
   choices), guide topic, example and `effects`: `reads`, `writes`, `renders`, `model` (an LLM call that costs
   money), `long` (minutes; may detach), `destructive` (deletes). Read it once per session.
2. **Always pass `--json`.** Every command prints exactly one JSON value:
   `{"v": 1, "command", "ok", "artifacts": [{"path", "kind"}], "items", "data", "next"}`. `artifacts` are the
   files this run wrote; open those, don't guess paths.
3. **Branch on `code`, not on the message.** A failure is `{"v": 1, "ok": false, "error", "code", "next",
   "exit"}`. Codes and exits are in `vedit guide errors`: `busy` (3) → `vedit wait`; `not_built` / `stale`
   (4) → run `next`; `bad_input` (4) → fix the file named in `error`; `missing_tool` / `no_disk` (5) →
   `vedit doctor` / `vedit clean`; `timeout` (124) → rerun, long stages resume.
4. **Preview what costs time or disk.** `--dry-run` reports what would run and writes nothing: `new` (files and
   media to build vs reuse), `cut` (cuts, boundaries to listen to, program pieces to render vs reused), `build`
   (pages to write, cut-outs to make), `subs` (batches to ask the model vs cached), `draft`/`render` (chunks,
   disk needed), `clean` (files to delete). `data.model_calls` counts Studio or model calls. Other commands
   reject the flag with `usage`.
5. **Never sleep-poll a job.** Long stages (`render`, `cut`, `transcribe`, `joins`) detach. `vedit wait
   --timeout S --json` blocks until the job ends: exit 0 done, 1 failed, 124 timed out (the job keeps running;
   call `wait` again). `--events` streams NDJSON progress on stderr: `{"t", "stage", "state", "chunk",
   "chunks", "frame", ...}`, one line per change.

Also:

- Confirmations never block: without a terminal they answer no. Pass `--yes` only when you mean it.
- Re-running any step is safe and incremental; prefer re-running over editing anything under `.vedit/`.
- `next` is the likely next command, not an order: follow it unless your plan says otherwise.
