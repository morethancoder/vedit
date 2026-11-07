# Footage-agnostic input and importer plugins

vedit takes any video file. Recorder-specific projects come in through importer plugins that live in the user's
config, never in the repo. Personal choices (logos, default style, examples) leave the code. Approved 2026-11-07.

Done when:
- [x] 1. nothing in the repo (code, tests, help, guide, README, docs, plans) names a particular recorder app
- [x] 2. any video file is input; project.yaml has a generic source `{file, camera?, trims?, mirror?}` for
      recorders that keep a clean camera track
- [x] 3. importer plugins: `vedit new <path>` asks each importer in `<config>/importers/` whether it knows the
      path; a match fills the generic source. `vedit importers` lists them, `vedit guide importers` documents the
      interface. The repo ships none; plain video needs none
- [x] 4. the old built-in recorder reader is a private importer (in `~/.config/vedit/importers/`, outside the repo) with its
      tests; `vedit new <recorder project>` behaves as before with the same media hashes
- [x] 5. `vedit clean`'s search for originals is an optional importer hook; no app folders or personal paths in
      code
- [x] 6. no personal defaults in code: fallback style is config.yaml's default else `base`; the octopus logo moves
      to the channel's logos; help and guide examples use neutral values
- [x] 7. evidence: git grep shows no recorder named, the acceptance recording via the private importer gives the
      same hashes, full tests pass, `make public` passes the checker

Out of scope (logged): Studio as a swappable local-AI backend.
