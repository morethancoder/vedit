# Phase 10: Agent-ready CLI

vedit already has `--json`, `next:` hints, `guide`, `skill`, `status` and documented exits 0/1/2. This phase
closes the gaps an agent hits when it drives vedit with no human watching.

Done when:
- [x] an agent can list every command and flag as data, branch on stable error codes, preview any expensive
      step, and wait on a detached job without sleep-polling
- [x] `vedit guide agents` documents all four, within the guide budget

## Children

- [`feature-introspect.md`](feature-introspect.md) — `vedit commands --json`: every command, flag, guide topic, side effects
- [`feature-errors.md`](feature-errors.md) — stable error codes and exit codes in every failure
- [`feature-dry-run.md`](feature-dry-run.md) — `--dry-run`: what a step would do and cost, no side effects
- [`feature-wait.md`](feature-wait.md) — `vedit wait`: block on a detached job, with a timeout and NDJSON events

## Refs

- `../principles.md` § Commands, § Agent-first; `vedit/cli.py`, `vedit/report.py`, `vedit/state.py`
