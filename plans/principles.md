# Principles

The rules every leaf respects. Pin this file whenever working on any node.

Done when:
- [ ] every rule below is concrete enough to check against a finished leaf
- [ ] rules enforced by tooling (ruff, tests) link to that tooling instead of repeating it

## The one idea

Mechanics in code, creativity in data. If the model would have to decide it again for the next video, it is a
default in vedit. If it changes per video (what to cut, what to show, what it says), it lives in `cuts.yaml`,
`cues.yaml`, `custom/` or a style pack. A leaf that makes the model re-decide a settled thing is not done.

## Extraction

- Lift working code from the sources in `docs/sources.md`; keep its numbers (they were tuned by ear and eye).
- Remove video-specific constants (clip names, durations, `DURATIONS = {"A": 928.45}`) into project.yaml or
  derived values.
- Language-aware from the start: Arabic normalisation, RTL, fonts per language; nothing assumes English.

## Local AI

- Every model run goes through `vedit/studio.py` → `studio --json`. No ML packages in vedit's dependencies.
- Classic CV and signal processing (OpenCV Haar, silence, loudness, brightness) stay in vedit.
- A temporary non-Studio fallback (e.g. `hyperframes remove-background`) is marked `# TEMP(studio-cutout)` and
  listed in phase 06.

## Commands

- One stage per command, verb names, lowercase (`vedit cut`, not `vedit apply-cuts`).
- Short human report by default, exactly one JSON value with `--json`; reports show problems and decisions only.
- Idempotent and incremental by content hash; never by file date.
- Long jobs run detached, log to `.vedit/logs/`, publish progress in `.vedit/state.json`.
- Destructive actions list targets with sizes and ask (`--yes` to skip).

## Agent-first

- Any agent drives vedit with no outside docs: `vedit guide` is the map (≤ 60 lines), `vedit guide <topic>` the
  detail (≤ 150 lines), `vedit <cmd> --help` the flags. Detail is opened only when needed; a test enforces budgets.
- A leaf that adds or changes a command updates its guide topic in the same commit.
- Reports end with a `next:` line; errors say what to run or write next.
- vedit renders and measures; the agent and the creator judge the look. vedit never calls a model to judge style.

## Style packs

- Template mechanism (decided phase 04, settled phase 05): a mustache subset in `vedit/graphics/pack.py`
  (`{{x}}`, `{{&x}}` raw, `{{#x}}`/`{{^x}}` sections, dotted names, `{{.}}`), no logic beyond it. Computation
  (times, layout, tokens) is the engine's; the template only places values.
- Each `types/<type>.html` declares its slots in a `<!-- vedit slots: ... -->` header; cues are validated
  against it (unknown field = error). Shared fragments are `partials/*.html`, pulled in as `{{&part.<name>}}`.
- Context names are a contract, listed in `vedit/graphics/pages.py`: `th.*` theme, `c.*` colours, `font.*`,
  `m.*` motion, `logo.*`, `part.*`, plus per-type values. Pack decisions (eases, exit timing) are tokens, not
  literals in templates.
- A pack is checked whole before use (`pack.check`): every problem at once. GSAP is bundled, never a CDN.

## Media

- ffmpeg on VideoToolbox (`-hwaccel videotoolbox`, `h264_videotoolbox`/`hevc_videotoolbox`); CPU only where no
  GPU encoder exists (VP9 alpha), commented.
- Every subprocess: time-boxed (`timeout` + `nice`), stdin closed.
- Generated files go under the project's `.vedit/`; nothing in `/tmp`, `~/Desktop`, `~/Downloads`.

## Code

- Python ≥ 3.12, uv, ruff (format + lint). Modules under ~400 lines; split by stage, not by helper type.
- Tests: pytest with small fixtures (a few seconds of audio/video cut from the Telegram project into
  `tests/fixtures/`, committed). Pure logic (time mapping, anchors, placement, snapping) gets unit tests.
- Pin external tool versions in one place (hyperframes, opencv).
- CLI: stdlib argparse subcommands, no CLI dependency (decided 2026-11-05: fewer deps, enough for verb + flags).

## Definition of done (every leaf)

- Its `Done when` boxes checked, each verified by running it, not by reading code.
- `ruff` clean, tests green, docs touched if behaviour or formats changed (`docs/formats.md` is the contract).
- One commit per leaf, message names the leaf.
