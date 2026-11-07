# Platforms and safe zones

One registry every other leaf reads.

Done when:
- [x] `vedit/formats/platforms.json`: per placement (youtube, youtube-shorts, instagram-reels, -stories, -feed-4x5,
      -feed-1x1, tiktok, facebook-reels, -stories, -feed, snapchat, x, linkedin-vertical, -feed, pinterest,
      telegram-stories, whatsapp-status) the canvas, aspect, safe insets, named HUD regions, crops elsewhere
      (grid 3:4, feed 4:5), max length, sources and confidence; values from the research file, the strictest
      credible source per edge where they conflict, unknown platforms falling back to the strictest 9:16 zone
- [x] `vedit formats [--json] [PLATFORM…]`: canvas, aspect, safe box and the union safe box of several platforms
- [x] `vedit guide formats`: what each aspect shows of a 16:9 frame, what each crop hides, where text may go
