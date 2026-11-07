# Platform UI safe zones (researched 2026-11-07)

All insets are px on the stated canvas. Almost no platform publishes official pixel values; most numbers come from third-party tools/blogs. Machine-readable: `platform-safe-zones.json`. `null` = unknown.

Key caveat: adkit.so (updated 2026-10-21) is one aggregator and supplies most of the figures; it says it mixes official guidance with estimated buffers without labelling which. Official sources found: Google universal video ad safe zones PDF (graphic only, no numbers), Pinterest pin specs (canvas only), Meta Business Help article on text overlays/safe zones for Stories and Reels ads (could not be read; Meta Reels ads guide copy cites 14% top / 35% bottom / 6% sides).

## Summary

| id | canvas | top | bottom | left | right | confidence |
|---|---|---|---|---|---|---|
| youtube-long-16x9 | 1920x1080 | None | None | None | None | low |
| youtube-shorts | 1080x1920 | 288 | 672 | 48 | 192 | low |
| instagram-reels | 1080x1920 | 269 | 672 | 65 | 227 | medium |
| instagram-stories | 1080x1920 | 269 | 672 | 65 | 65 | medium |
| instagram-feed-4x5 | 1080x1350 | 135 | 135 | 108 | 108 | low |
| instagram-feed-1x1 | 1080x1080 | 108 | 108 | 108 | 108 | low |
| tiktok | 1080x1920 | 240 | 660 | 120 | 120 | medium |
| facebook-reels | 1080x1920 | 269 | 672 | 65 | 227 | medium |
| facebook-stories | 1080x1920 | 269 | 672 | 65 | 65 | medium |
| facebook-feed-video | 1080x1350 | 135 | 135 | 108 | 108 | low |
| snapchat-spotlight-stories | 1080x1920 | 192 | 672 | 65 | 65 | low |
| x-video | 1080x1920 | 80 | 450 | 80 | 80 | low |
| linkedin-video-vertical | 1080x1920 | 260 | 560 | 112 | 210 | low |
| linkedin-video-feed | 1080x608 | 40 | 40 | 45 | 45 | low |
| pinterest-video-pin | 1080x1920 | 270 | 440 | 65 | 195 | low |
| telegram-stories | 1080x1920 | None | None | None | None | low |
| whatsapp-status | 1080x1920 | None | None | None | None | low |

## youtube-long-16x9
- Canvas: [1920, 1080] ; aspects: 16:9
- Safe insets: {'top': None, 'bottom': None, 'left': None, 'right': None}
- Region end-screen inner safe area (editor rule): x=192 y=108 w=1536 h=864 - end-screen elements must sit inside inner 80% (10% margin per edge) per third-party checker; YouTube Studio also rejects 'Element outside safe area'
- Region player controls/progress bar: x=0 y=None w=1920 h=None - bottom strip; no official pixel height found
- Region title/channel overlay on hover: x=0 y=0 w=1920 h=None - top strip on hover; no official pixel height found
- Sources: https://www.collabpals.com/tools/youtube-end-screen-previewer (2026 (undated)); https://services.google.com/fh/files/misc/universalsafezones-youtube.pdf (undated; graphic only, no numbers)
- Confidence: low. No official pixel values. Insets given as null; regions with null y/h unknown. Fallback inference: 10% margin each edge (192 px sides, 108 px top/bottom).

## youtube-shorts
- Canvas: [1080, 1920] ; aspects: 9:16
- Safe insets: {'top': 288, 'bottom': 672, 'left': 48, 'right': 192}
- Region right action column: x=888 y=288 w=192 h=960 - like/dislike/comment/share/remix (adkit: safe rect x48-888, y288-1248)
- Region bottom channel/title/sound: x=0 y=1248 w=1080 h=672 - channel, subscribe, title, music
- Sources: https://adkit.so/tools/safe-zones/youtube (2026-10-21); https://adaptlypost.com/en/blog/social-media-safe-zones-2026-complete-guide (2026 (undated)); https://services.google.com/fh/files/misc/universalsafezones-youtube.pdf (undated)
- Confidence: low. Conflict: adaptlypost top120/bottom300(360 desc open)/right96; adkit top288/bottom672/left48/right192; other tools 840x960..984x1500 safe rect. Shorts end screens: one source says unsupported (unverified).

## instagram-reels
- Canvas: [1080, 1920] ; aspects: 9:16
- Safe insets: {'top': 269, 'bottom': 672, 'left': 65, 'right': 227}
- Region right action column: x=853 y=1152 w=227 h=768 - like/comment/share/audio (adkit, lower-right block below y=1152)
- Region bottom caption/username/audio: x=0 y=1248 w=1080 h=672 - account, caption, audio pill
- Region top bar: x=0 y=0 w=1080 h=269 - Reels label, camera icon
- Crop (profile grid): 3:4 (1080x1440 center crop; some sources 1013x1350)
- Crop (main feed): 4:5 (center 1080x1350; some sources only)
- Crop (Reels tab): 9:16 full
- Sources: https://adkit.so/tools/safe-zones/instagram (2026-10-21); https://adaptlypost.com/en/blog/social-media-safe-zones-2026-complete-guide (2026); https://www.kapwing.com/resources/instagrams-new-grid-layout-size-and-dimensions-2025/ (2025-12-30); https://billo.app/blog/meta-ads-safe-zones (2026-06-16)
- Confidence: medium. Conflict: adaptlypost top210/bottom310(390 sponsored)/right84; billo (1440x2560 canvas) top14% bottom20-35% sides 6%; Meta Reels ads guide copy: 14/35/6 %; adkit 269/672/65. Safe 14/35/6 on 1080x1920 = 269/672/65. Grid 3:4 confirmed by Kapwing; Reel-in-feed 4:5 only blogs.

## instagram-stories
- Canvas: [1080, 1920] ; aspects: 9:16
- Safe insets: {'top': 269, 'bottom': 672, 'left': 65, 'right': 65}
- Region top bar (progress, avatar): x=0 y=0 w=1080 h=269 - progress bars, profile row
- Region bottom reply bar: x=0 y=1248 w=1080 h=672 - send message/reactions (conservative)
- Sources: https://adkit.so/tools/safe-zones/instagram (2026-10-21); https://adaptlypost.com/en/blog/social-media-safe-zones-2026-complete-guide (2026); https://billo.app/blog/meta-ads-safe-zones (2026-06-16)
- Confidence: medium. Conflict: adaptlypost top100/bottom200; billo/older guides 14% top (~270) /14-20% bottom (270-380); adkit 269/672. Claimed March 2026 unified FB+IG Stories/Reels zone: single source (billo), unverified.

## instagram-feed-4x5
- Canvas: [1080, 1350] ; aspects: 4:5
- Safe insets: {'top': 135, 'bottom': 135, 'left': 108, 'right': 108}
- Crop (profile grid): 3:4 center crop
- Sources: https://adkit.so/tools/safe-zones/instagram (2026-10-21)
- Confidence: low. Insets are adkit optional buffers (10%), not Meta requirements. Native controls only overlay at bottom briefly (mute icon).

## instagram-feed-1x1
- Canvas: [1080, 1080] ; aspects: 1:1
- Safe insets: {'top': 108, 'bottom': 108, 'left': 108, 'right': 108}
- Crop (profile grid): 3:4 center crop
- Sources: https://adkit.so/tools/safe-zones/instagram (2026-10-21)
- Confidence: low. Optional 10% buffer, not official.

## tiktok
- Canvas: [1080, 1920] ; aspects: 9:16
- Safe insets: {'top': 240, 'bottom': 660, 'left': 120, 'right': 120}
- Region right action column: x=780 y=840 w=300 h=1080 - like/comment/bookmark/share/profile (In-Feed template: right margin 300 below y=840)
- Region bottom caption/sound: x=0 y=1260 w=1080 h=660 - username, caption, sound ticker
- Region top tabs: x=0 y=0 w=1080 h=240 - Following/For You, search
- Crop (profile grid): 3:4 (approx; not verified)
- Sources: https://adkit.so/tools/safe-zones/tiktok (2026-10-21); https://www.trymypost.com/blog/tiktok-ad-specs-2026-safe-zones (2026-02-15); https://adaptlypost.com/en/blog/social-media-safe-zones-2026-complete-guide (2026)
- Confidence: medium. Ads templates: In-Feed 240/660/120/120 (right 300 below y840); Anchor 4-line caption 252/1014/120/120 (right 240 below y360). Organic conflicts: adaptlypost 108/320(370 ads)/L60/R120; trymypost 150/350-400/R120; catalog-API 483-484 bottom. TikTok publishes downloadable templates, no px in help page. Grid crop figure unverified.

## facebook-reels
- Canvas: [1080, 1920] ; aspects: 9:16
- Safe insets: {'top': 269, 'bottom': 672, 'left': 65, 'right': 227}
- Region right action column: x=853 y=1152 w=227 h=768 - like/comment/share buttons
- Sources: https://adkit.so/tools/safe-zones/facebook (2026-10-21); https://adaptlypost.com/en/blog/social-media-safe-zones-2026-complete-guide (2026)
- Confidence: medium. adaptlypost: top100 bottom300. Same Meta 14/35/6 basis as IG Reels.

## facebook-stories
- Canvas: [1080, 1920] ; aspects: 9:16
- Safe insets: {'top': 269, 'bottom': 672, 'left': 65, 'right': 65}
- Sources: https://adkit.so/tools/safe-zones/facebook (2026-10-21); https://billo.app/blog/meta-ads-safe-zones (2026-06-16)
- Confidence: medium. billo Stories-only: 14% top/14% bottom (358 px on 1440x2560 -> ~269/269 on 1080x1920).

## facebook-feed-video
- Canvas: [1080, 1350] ; aspects: 4:5, 1:1, 16:9
- Safe insets: {'top': 135, 'bottom': 135, 'left': 108, 'right': 108}
- Sources: https://adkit.so/tools/safe-zones/facebook (2026-10-21)
- Confidence: low. Optional buffers (1080x1080: 108 all; 1080x1350: 135/135/108/108; 1080x608: 61/61/80/80), not Meta requirements.

## snapchat-spotlight-stories
- Canvas: [1080, 1920] ; aspects: 9:16
- Safe insets: {'top': 192, 'bottom': 672, 'left': 65, 'right': 65}
- Region lower-right exclusion: x=918 y=1056 w=162 h=864 - Spotlight/ad buttons
- Sources: https://adkit.so/tools/safe-zones/snapchat (2026-10-21); https://benly.ai/learn/snapchat-ads/snapchat-ad-specs-formats (2026); https://help.zuuvi.com/en/articles/8907258-social-content-safe-zones-keep-it-all-visible (2025)
- Confidence: low. Conflict: 150 top/bottom (benly, spilno, zuuvi 149); adkit 192/672 (10%/35%); other adkit-snapchat reading ~230/384; auditsocials 210/200. Snap publishes no single px safe zone (moda.app). No Spotlight-specific data found.

## x-video
- Canvas: [1080, 1920] ; aspects: 9:16, 16:9, 1:1
- Safe insets: {'top': 80, 'bottom': 450, 'left': 80, 'right': 80}
- Sources: https://adkit.so/tools/safe-zones/x (2026-10-21)
- Confidence: low. adkit states these are NOT official and unverified vs X's Vertical Video diagram. Landscape 1080x608 buffers 40/40/45/45 (adkit linkedin page values differ).

## linkedin-video-vertical
- Canvas: [1080, 1920] ; aspects: 9:16
- Safe insets: {'top': 260, 'bottom': 560, 'left': 112, 'right': 210}
- Sources: https://adkit.so/tools/safe-zones/linkedin (2026-10-21); https://adaptlypost.com/en/blog/social-media-safe-zones-2026-complete-guide (2026)
- Confidence: low. Conflict: adaptlypost top100/bottom100 (996/1010x1720 zone). adkit says measures video interface.

## linkedin-video-feed
- Canvas: [1080, 608] ; aspects: 16:9, 1:1, 4:5
- Safe insets: {'top': 40, 'bottom': 40, 'left': 45, 'right': 45}
- Sources: https://adkit.so/tools/safe-zones/linkedin (2026-10-21)
- Confidence: low. Optional spacing only. Adkit universal feed landscape uses 61/61/80/80 instead.

## pinterest-video-pin
- Canvas: [1080, 1920] ; aspects: 9:16, 1:2, 2:3, 3:4, 4:5, 1:1
- Safe insets: {'top': 270, 'bottom': 440, 'left': 65, 'right': 195}
- Sources: https://help.pinterest.com/en/article/review-pin-specs (undated (official: 9:16 / 1080x1920 recommended)); https://adaptlypost.com/en/blog/social-media-safe-zones-2026-complete-guide (2026); https://moda.app/resources/sizes/pinterest-idea-pin (undated)
- Confidence: low. Severe conflict: adaptlypost 100/220; others 170/340, 180/260, 270/440 (L65/R195). Chosen row = most conservative. Canvas official, insets not.

## telegram-stories
- Canvas: [1080, 1920] ; aspects: 9:16
- Safe insets: {'top': None, 'bottom': None, 'left': None, 'right': None}
- Sources: none
- Confidence: low. No data found. Use generic 250 px top/bottom (third-party blog) or the Instagram Stories zone as a stand-in.

## whatsapp-status
- Canvas: [1080, 1920] ; aspects: 9:16
- Safe insets: {'top': None, 'bottom': None, 'left': None, 'right': None}
- Sources: none
- Confidence: low. No data found. Use Instagram Stories zone as stand-in.
