# Program render

The cut film the graphics sit on, rebuilt in seconds after a small change.

Done when:
- [x] proxy (1080p30) and master (4K60) profiles; picture via VideoToolbox, holds as held frames
- [x] audio: 48 kHz, 60 ms equal-power crossfades at every join, silent holds, end fade
- [x] pieces cached by hash; editing one cut re-encodes only the touched pieces before a lossless concat

## Refs

- port T `tools/program.py`; incremental render is new
