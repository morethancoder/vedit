# Draft and render per output

Done when:
- [x] `vedit draft [OUTPUT]` and `vedit render [OUTPUT]` work per output (default: all); short-form masters are
      1080×1920 (or the output canvas) at 60 fps, the YouTube master stays 4K60
- [x] finished files are named `<slug>-<output-id>.mp4` under `.vedit/renders/`

(as flags: `vedit draft --output ID|all`, `vedit render --output ID|all` (detached; `vedit wait`). Drafts are
`draft-<id>.mp4`. Telegram talk: reel-1 17.6 s final in 35 s, story-bot 127 s final in 300 s, both 1080x1920 60 fps.)
