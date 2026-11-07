# vedit draft

The creator reviews a file, not a browser editor.

Done when:
- [x] renders 1080p (`--quality draft`, `--gpu --browser-gpu`) to `.vedit/renders/draft.mp4`
- [x] uses the same layering as the master: the same full-frame `.vedit/hf/` composition, only at 1080p (overlay mode was not adopted), so the draft shows exactly what the master will
- [x] opens it with `open -a "QuickTime Player"`; never starts a HyperFrames Studio preview
- [x] fast enough to iterate on: per chunk, 2 at a time, fast capture off, only changed chunks re-rendered
      (13:08 film: 1528 s → 411 s; numbers in `docs/pipeline.md` § draft)
