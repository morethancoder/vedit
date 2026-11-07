---
summary: exit codes, error format, what to do when a command fails
next: vedit status
---
# Errors and exit codes

## Codes and exit codes

Every failure carries a stable `code`. Branch on the code, never on the English message.

| code | exit | meaning | usual fix |
|---|---|---|---|
| `failed` | 1 | the step ran and failed | read the message and `.vedit/logs/<stage>.log` |
| `usage` | 2 | wrong flags or arguments | `vedit <cmd> --help`, `vedit commands --json` |
| `busy` | 3 | a job is running in this project | `vedit wait`, then retry |
| `not_built` | 4 | an earlier step's output is missing | run the `next` command |
| `stale` | 4 | an earlier step's output is out of date | run the `next` command |
| `bad_input` | 4 | a file you wrote or a flag value is wrong | fix the named file or value |
| `missing_tool` | 5 | ffmpeg, npx, Studio or a model is missing | `vedit doctor` |
| `no_disk` | 5 | not enough free space | `vedit clean`, then retry |
| `timeout` | 124 | a time-boxed step ran out of time | rerun; long stages resume |

`0` is ok: the report has no failed line. A report with a failed line (no exception) exits `1`.

## Error format

Text mode prints to stderr:

```
error: <what went wrong>  [<code>]
next: <what to run or write next>
```

With `--json` the one value on stdout is
`{"v": 1, "ok": false, "error": "...", "code": "...", "next": "...", "exit": 4}`.
A successful report has `v`, `command`, `ok`, `artifacts` (`[{"path", "kind"}]`: files this run wrote),
`items`, `data`, `next`.

## What to do

- Read `next:` first and do it. It is the likely fix, not a guarantee.
- "not built yet": the command is planned. Run `vedit guide` to see which commands exist; do not retry.
- "no project.yaml": run inside the project folder, pass `--project PATH`, or create one with `vedit new`.
- Studio unreachable or a model missing: start the Studio app or download the model there, then `vedit doctor`.
- Tool missing or too old: `vedit doctor` lists each check and the fix.
- A render or other long job died: `vedit status` shows the log tail and path; re-run the stage, it resumes.
- A job is running (`busy`): `vedit wait` blocks until it ends (`--timeout S`); never sleep-poll.
- Unknown guide topic: `vedit guide --list`.

## Flags every command accepts

`--json` (one JSON value), `--project PATH` (project folder, default: walk up from the current folder),
`--yes` (answer yes to confirmations). Destructive actions list what they touch and ask first; without a
terminal they refuse unless `--yes` is given.
