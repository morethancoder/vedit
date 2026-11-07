# HUD check

Done when:
- [x] `vedit review` flags (`hud`) every graphic or caption box that enters a HUD region of any target platform,
      with the platform and the element named
- [x] the review sheet and `vedit draft --hud` draw a mock of the platform UI (regions labelled) over the frame

(the mock is `.vedit/review/hud-<output>.jpg`, drawn by `vedit review` from the output's draft; there is no
separate `vedit draft --hud`. Placement now also keeps captions, text bands and cards clear of action columns
that reach past the side inset (`formats.clear_span`). Telegram talk: 0 hud flags on reel-1, story, post.)
