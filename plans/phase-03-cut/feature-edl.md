# Edit decision list

Turn resolved cuts into the program's pieces.

Done when:
- [x] boundaries snap to the quietest 10 ms within 0.12 s; ranges on a 1/30 s grid
- [x] pauses > 0.5 s become 0.3 s; chapter holds are 1.8 s silent held frames; `fade_start` = end of last word
- [x] alternate camera jump cuts carry a 1.07× punch-in flag (unit-tested; 64 on the fixture)
- [ ] the edl for the fixture matches T's `work/edl.json` piece count and total within one frame (open: with refine, 160 vs 160 pieces but 790.37 vs 788.10 s and 271/320 boundaries within 2 frames: the fixture is a new ASR transcription, so refine picks differ; T's own words + refined.json through the port match exactly, 0.0000 s)

## Refs

- port T `tools/cuts.py` (snapping, pauses) and `build.py` `zoom_plan`
