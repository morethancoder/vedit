# Phase 01: Foundation

The package, command skeleton and shared helpers every later phase plugs into.

Done when:
- [x] `uv tool install -e .` puts `vedit` on PATH; `vedit --help` lists the planned commands
- [x] `vedit doctor` and `vedit status` work on an empty and on a real project
- [x] a fresh agent that only runs `vedit guide` can name the edit loop and which files it must write

## Children

- [`feature-package.md`](feature-package.md) — pyproject, layout, ruff, pytest, Makefile, fixtures
- [`feature-project-file.md`](feature-project-file.md) — `project.yaml` schema, project discovery, `.vedit/` paths
- [`feature-run-helpers.md`](feature-run-helpers.md) [P] — subprocess, ffmpeg presets, logging, reports, `--json` (parallel with studio-client)
- [`feature-studio-client.md`](feature-studio-client.md) [P] — `vedit/studio.py` over `studio --json` (parallel with run-helpers)
- [`feature-status-doctor.md`](feature-status-doctor.md) — `.vedit/state.json`, `vedit status`, `vedit doctor`
- [`feature-guide.md`](feature-guide.md) — `vedit guide [topic]`, `vedit skill [install]`, short help, `next:` lines, line budgets

## Refs

- `../../docs/architecture.md`, `../../docs/formats.md`
