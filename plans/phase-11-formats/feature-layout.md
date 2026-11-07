# Graphics on any canvas

Done when:
- [x] compose writes the composition at the output's canvas (not fixed 1920×1080); style packs get canvas size
      and safe box as CSS variables
- [ ] placement keeps every graphic inside the output's safe box (union of its platforms); a cue that can't fit is
      reported, not squeezed
- [x] the same cues.yaml builds for 16:9 and 9:16 outputs with no per-output edits

(open box 2: text graphics go into a band under the face inside the safe box, cards are centred in it, big words
span the crop; the per-graphic check that nothing leaves the box is the HUD check leaf. Known gap: 16:9 doodles
and screens shrink to 56 % as cards in 9:16 and read small; a vertical layout for those scenes is a follow-up.
Telegram talk: `vedit build` wrote reel-1, story and post in 2 s; the reel draft renders 1080x1920 in 25 s.)
