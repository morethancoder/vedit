---
summary: aspects, what each crop shows, platform HUD safe zones, where text may go
next: vedit formats
---
# Formats and platforms

One recording can become several outputs: the 16:9 YouTube film, 9:16 clips (Reels, Shorts, TikTok), stories
and 4:5 or 1:1 feed posts. Each output has an aspect and target platforms; every platform covers part of the
frame with its own UI (the HUD). `vedit formats` prints the numbers; this page explains them.

## Aspects

| aspect | canvas | used for |
|---|---|---|
| 16:9 | 1920×1080 (master 3840×2160) | YouTube, LinkedIn/X/Facebook landscape |
| 9:16 | 1080×1920 | Reels, Shorts, TikTok, Stories, Snapchat, Pinterest, Telegram/WhatsApp status |
| 4:5 | 1080×1350 | Instagram and Facebook feed (takes the most room in the feed) |
| 1:1 | 1080×1080 | feed posts, LinkedIn, X |
| 3:4, 2:3 | 1080×1440, 1080×1620 | Pinterest; 3:4 is also the Instagram profile grid crop |

## What a crop of the 16:9 recording shows

A full-height crop keeps this much of the landscape frame's width (the crop follows the face):

- 9:16: **31.6 %** (608 of 1920 px). One person fills it; a slide, a screen or a second person does not fit.
- 3:4: 42.2 % (810 px). 4:5: 45 % (864 px). 1:1: 56.2 % (1080 px).

So a screen recording or slide shown in 16:9 needs its own treatment in 9:16 (shown as a graphic card, not
cropped), and anything placed at the sides of the 16:9 frame is lost.

## What other places cut from a 9:16 video

- Instagram profile grid shows a centered **3:4**: the top and bottom 240 px (12.5 % each) are hidden.
- A Reel shown in the main feed may be cropped to **4:5**: top and bottom 285 px hidden.
- A 1:1 preview hides 420 px top and bottom.

Put the hook (first words, title) in the middle band (y 285–1635 on 1080×1920) so every preview shows it.

## HUD safe zones (1080×1920 unless noted)

Insets: how far from each edge the platform UI reaches. Keep captions and graphics inside.

| platform | top | bottom | left | right | what covers it |
|---|---|---|---|---|---|
| Instagram / Facebook Reels | 269 | 672 | 65 | 227 | top bar; caption, user, audio; action column |
| Instagram / Facebook Stories | 269 | 672 | 65 | 65 | progress bar, profile; reply bar |
| TikTok | 240 | 660 | 120 | 120 | tabs; caption, music; action column |
| YouTube Shorts | 288 | 672 | 48 | 192 | search, menu; title, channel; actions |
| Snapchat | 192 | 672 | 65 | 65 | header; caption, reply |
| LinkedIn vertical | 260 | 560 | 112 | 210 | |
| Pinterest | 270 | 440 | 65 | 195 | |
| X | 80 | 450 | 80 | 80 | |
| Telegram, WhatsApp status | 288 | 672 | 120 | 227 | no published data: strictest of the above |
| feed 4:5 (1080×1350) | 135 | 135 | 108 | 108 | |
| YouTube 16:9 | 54 | 108 | 96 | 96 | convention: player controls on hover |

The bottom **35 %** of a 9:16 short is the most dangerous area: captions, usernames and audio pills sit there
on every platform. Burned-in captions go above it.

An output with several platforms uses the strictest inset per edge (`vedit formats instagram-reels tiktok
youtube-shorts` prints that box: x 120–853, y 288–1248 for those four with Facebook Reels).

## How sure these numbers are

Platforms rarely publish pixels. Values come from Meta's Reels guidance (14 % top, 35 % bottom, 6 % sides),
ad-template makers and design tools, dated 2025–2026; where sources disagree vedit takes the strictest.
`vedit formats --json` gives each platform's sources and a confidence (`medium` or `low`). Full research:
`docs/research/platform-safe-zones.md` in the vedit repo. Platforms change their UI: when a review flag looks
wrong, compare with a screenshot from the app.

## Making clips, shorts, stories and posts

One project keeps one cut and one `cues.yaml`; each output re-frames them. The 16:9 film is always there
(`youtube`). Add the others, then build, check and render:

```
vedit output add reel-1 --from "first words" --to "last words" --near "A 245"     # 9:16 clip from the talk
vedit output add story-1 --kind story --from "..." --to "..." --near "A 300"     # split into <= 60 s parts
vedit output add post --kind post --platforms instagram-feed,facebook-feed       # 4:5, whole cut
vedit reframe --sheet          # the face-following crop drawn on 16 frames: .vedit/reframe/<id>.jpg
vedit build                    # the film + every output (.vedit/out/<id>/hf/)
vedit draft --output reel-1    # 30 fps draft, opened in QuickTime
vedit review                   # [hud] flags + .vedit/review/hud-<id>.jpg (platform UI drawn on the draft)
vedit render --output all      # 60 fps finals: .vedit/renders/<slug>-<id>.mp4 (+ -NN parts for stories)
```

- Kinds: `clip` (needs `--from`/`--to` words), `short` (the whole cut in 9:16; recordings shot vertical are not supported yet), `story` (optional
  range; split at pauses under the platform limit), `post` (4:5 or 1:1). Default platforms per kind:
  `vedit output list --json`. Captions are burned in for every kind but `master` (`--captions srt|none`).
- On camera, labels, chips and kinetic lines go under the face, above the captions (the captions pause when
  there is no room). Big words span the crop behind the head. Chapters, doodles and screens become a card
  centred in the safe box, narrowed when a platform's side buttons reach into its rows.
- Write cues for the 16:9 film; the outputs follow. A `[hud]` flag names the graphic and the platform UI it
  runs into: shorten its text, or move its words in `cues.yaml`.
