# Built-in manual: guide, skill, help

Any agent can learn vedit from vedit itself, paying only for the detail it needs right now.

Done when:
- [x] `vedit guide` prints one screen (≤ 60 lines): what vedit is, the edit loop as commands, the files the agent writes, how to go deeper. Ends with the topic list.
- [x] `vedit guide <topic>` prints one topic (≤ 150 lines): `cuts`, `cues`, `styles`, `style-authoring`, `channels`, `review`, `render`, `traps`, plus one topic per cue type (`cue-label`, `cue-doodle`, …). `vedit guide --list` lists topics with one line each.
- [x] `vedit <cmd> --help` stays short (usage, flags, one example) and names its guide topic; every report ends with a `next:` line naming the likely next command
- [x] `vedit skill` prints the agent skill (agent-neutral markdown: when to use vedit, the loop, "run `vedit guide <topic>` before writing X"). `vedit skill install` writes a ≤ 10-line pointer SKILL.md to `~/.claude/skills/vedit/` and prints an AGENTS.md snippet for other agents; it never copies the full text
- [x] a test fails when any guide page goes over its line budget or names a command/flag the CLI doesn't have
- [x] errors say what to do next (`no cues.yaml — run vedit guide cues, then write cues.yaml`), exit codes documented in `vedit guide errors`

## Approach

Guide pages are markdown files inside the package (`vedit/guide/*.md`), shipped with it, so nothing is
downloaded. Phase 01 ships the overview, `skill`, `errors` and stubs; each later leaf writes or updates its own
topic as part of its definition of done (see principles: Agent-first). Unbuilt commands appear in the overview
marked `(not built yet)`.

## Refs

- depends on: [`feature-package.md`](feature-package.md), [`feature-run-helpers.md`](feature-run-helpers.md) (report + `next:` line)
