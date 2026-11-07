# Package skeleton

A Python package `vedit` with the module layout from docs/architecture.md and the dev loop around it.

Done when:
- [x] `pyproject.toml` (Python ≥ 3.12, deps: pyyaml, numpy, soundfile, opencv-python-headless==4.10.0.84, numpy<2) and `uv tool install -e .` works
- [x] `vedit --help` shows every planned command; unbuilt ones print "not built yet (phase NN)" and exit 2
- [x] Makefile (makefile-standards skill: one-word targets, `help` default) with `test`, `lint`, `install`, `clean` (prints what it freed); `tests/fixtures/` holds a 10 s Arabic clip cut from the Telegram project

## Approach

Plain `argparse` subcommands or a tiny dependency (decide, note it in principles). Command table in `cli.py`
maps each verb to a module function returning a report object; the CLI layer prints text or JSON.
`git init` here if not done, `.gitignore` for `.venv`, `__pycache__`, `.vedit/`, `.playwright/`.
