# youtube-edit skill on vedit

The skill holds taste; vedit holds mechanics.

Done when:
- [x] `~/.claude/skills/youtube-edit/SKILL.md` workflow = the vedit command sequence + what the model writes at each step (cuts.yaml, cues.yaml, custom/)
- [x] no script paths, template copying or pipeline numbers remain in the skill (they live in vedit docs)
- [ ] a fresh session asked to "edit this video for YouTube" reaches a draft using only the skill + vedit
- [x] the skill text lives in vedit (`vedit skill`); `~/.claude/skills/youtube-edit/SKILL.md` keeps only the creator's taste rules and "run `vedit guide`"
- [ ] token check: the fresh session's vedit help reads (guide + topics opened) stay under ~3k tokens before the first edit command
      (static count: `vedit skill` 569 + `vedit guide` 352 words ≈ 1.3k tokens; the fresh-session run is still open)

## Notes

- Written by a 3-way `workflow-compare` run (Opus solo won, 8.0; `~/.claude/skills/workflow-compare/results.md`).
  The workflow lives in `vedit/guide/skill.md`; the taste skill's source is `docs/youtube-edit-SKILL.md`, copied to
  `~/.claude/skills/youtube-edit/SKILL.md` (old one: `~/.claude/skills/youtube-edit.SKILL.md.2026-11-05.bak`).
- Open: "screen recordings sped up to fit their line" has no screen-cue speed field yet.
