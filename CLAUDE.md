# vedit: working notes for Claude

Read `README.md`, then `plans/plan.md` and `plans/principles.md` before touching code. Work one leaf at a time
(`plans/phase-*/feature-*.md`), check its `Done when` boxes when it truly holds, one commit per leaf.

- **Extract, don't invent.** Almost every feature already exists as working code in
  `~/Demos/tele-a7-growth-story/` (Arabic, yellow) or `~/Demos/claude-in-telegram-video/` (English, violet).
  `docs/sources.md` maps each feature to its source file. Read the source, lift it, make it generic.
- **Local AI goes through Studio** (`studio --json …`). Never add a model, torch, onnx or a background-removal
  package to vedit. Missing capability → a leaf in phase 06 (Studio additions), with a temporary fallback noted.
- Test against the real Telegram video project (`~/Demos/tele-a7-growth-story`, 13:08 cut of a 15:28 talk):
  it is the acceptance fixture. Don't delete or rewrite anything inside it; work on a copy.
- ffmpeg/ffprobe must be time-boxed (`timeout <s> nice -n 19 ffmpeg …`): a hook blocks bare calls.
- Never open HyperFrames Studio preview for review: render a draft and open the MP4 in QuickTime.
- Implement every leaf yourself, in the main session. Subagents only for reading a lot of material or
  summarizing (Haiku `reader` for mechanical sweeps, Sonnet `researcher` when relevance must be judged); never
  for writing vedit code. Each brief ends with a short report.
- No time estimates in plans or docs.
- **Footage-agnostic, no personal choices in code** (the creator, 2026-11-07). vedit takes any video file; never name
  or special-case a particular recorder app in the repo. Recorder support goes in importer plugins in the
  user's config (`~/.config/vedit/importers/`). Personal defaults (styles, logos, languages, paths, brands) live in
  `config.yaml` / channels, never as code defaults or base-pack assets; help examples stay neutral.
- **No blur by default** (2026-11-07). When footage doesn't fill the canvas (mixed shapes, pillarbox, letterbox) the
  default fill is a plain background. Blur is an option the user picks, never automatic; a shader background is
  another option. Applies to every new fill or background vedit adds.
- **The GitHub repo (github.com/morethancoder/vedit) is public and never gets personal data** (the creator, 2026-11-07).
  Publish only with `make publish MSG="what changed"`: it exports HEAD scrubbed, runs the tests on the export,
  checks tree, message and author (`scripts/public_check.py`) and pushes from `.public/` with the noreply author.
  Never push this repo, add a remote, or write to GitHub any other way: its history holds the personal email,
  name, home paths and the speech clip. Hooks enforce it (`.claude/hooks/guard-publish.sh`; git pre-push via
  `make guard`). If the checker flags something, fix the source or the scrub, never the checker's rules.
