# Reel composition polish

User review of `draft-reel-crash.mp4` (2026-11-07): "composition is terrible: art is not clear, text feels
misaligned, the person is not centred horizontally as it should be in talking videos." Approved 2026-11-07.

Done when:
- [x] 1. centring: each piece of a reframed output is centred on the median face position and re-centres fully
      (eased) when the speaker moves; on reel-crash the median face offset is <= 3% of the frame width
- [x] 2. captions and labels are centred on the frame's vertical axis, with symmetric margins (the right HUD
      rail's inset is mirrored on the left)
- [x] 3. no blur behind graphics: plain style background by default; blur only when asked (CLAUDE.md rule)
- [x] 4. doodles are re-laid for the vertical frame, in a split: the doodle in the top half on a plain background,
      the speaker in the bottom half; doodle labels >= ~36 px tall on a 1080-wide frame
- [x] 5. evidence: reel-crash re-rendered, frames looked at, zero HUD flags, face-offset numbers

Cause of 1 (found): `formats/reframe.py` starts each piece on the first face sample and only eases to the
edge of an 18% dead zone, so the face sits up to 18% off centre for a whole piece.

## Result (2026-11-07)

- 1: each piece starts on its whole-piece median face, follows a rolling median (about 1 s each way) once it
  leaves an 8% dead zone and eases until the face is within 2% of the centre (`reframe.PARAMS` v2). reel-crash:
  median offset 2.7% against the smoothed face (3.4% against raw samples; a perfectly still crop per piece
  scores 3.3%, which is the speaker's own head motion), down from 8.9%.
- 2: `Geometry.clear` mirrors the wider inset, so labels, kinetic lines and captions centre on the frame; label
  text is centred in its band.
- 3: outputs take `fill: plain | blur` (default plain): a plain style background comes up behind full-frame
  scenes; the A-roll blur happens only with `fill: blur`.
- 4: a doodle in a vertical output is a split. Its beats are drawn in pages (`doodles.spec.pages`) sized so that
  labels stay >= 38 px in the panel above the side buttons (578x504 for Reels+TikTok+Shorts). Captions move to
  the seam, and the camera zooms out about the face so the whole head sits below them. funnel: 4 pages, labels
  55 / 59 / 38-40 / 56 px.
- 5: reel-crash rebuilt and drafted, frames at 1.5, 8, 12, 18.8, 26 and 41 s looked at; `vedit review`: nothing
  enters the HUD on any of the 6 outputs. Suite: 739 passed.
