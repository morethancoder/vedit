# Video cut-out in Studio

`studio cutout VIDEO.mp4 --out matte.webm` (or ProRes 4444): the main person, frame by frame, stable over time.

Done when:
- [ ] per-frame matte (birefnet / birefnet-lite or a video matting model) with temporal smoothing, alpha video out
- [ ] a subject-only mode (largest person, face-anchored) so background objects like the bookshelf are excluded without vedit's mask hack
- [ ] on the Telegram "1.7M" range it matches or beats `hyperframes remove-background` + `matte_mask.py` by eye at 4K

## Refs

- current behaviour to replace: T `scripts/matte.sh`, `tools/matte_mask.py`
- seam to replace: `_make_matte` in `vedit/graphics/cutouts.py` (every fallback site is marked `# TEMP(studio-cutout)`; keep its signature, then drop `mask_matte`)
