# Face track

Where his face is, every quarter second, on the program.

Done when:
- [x] samples the proxy at 4 fps (OpenCV Haar, largest frontal face) → `[x,y,w,h]` + `cam` flag, indexed by real spacing
- [x] cached by source hash; mirrored camera handled
- [x] a debug sheet draws boxes on sampled frames for a quick eye check

## Refs

- port T `tools/faces.py`
