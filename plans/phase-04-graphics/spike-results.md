# Overlay-only render spike: results (2026-11-05)

Leaf: [`feature-overlay-spike.md`](feature-overlay-spike.md). Everything lives in `~/Demos/vedit-overlay-spike/`
(APFS clone of the Telegram project; the original was not touched). Scripts in `scripts/`, logs and
`*.metrics` in `logs/`, outputs and contact sheets in `out/`.

## Sample

No single chunk holds all six graphic types, so two chunk files of the real 4K render were used (192.6 s):

- `chunk-00` (0–149.9 s): big word behind the head with cut-out (`big-17m` + `mt-17m.webm`), punch-in zooms,
  chapter card over blur + dim (`chapter1`), two long doodles over blur (`dd-path`, `dd-request`), lower thirds.
- `chunk-05` (745.4–788.1 s): lower thirds, `try-ptb`, outro, end fade to black.
- **There is no screen-recording cue over blur in this film.** The phone screenshot (`ptb`) is over sharp
  footage. Blur regions are tested by the chapter card and the doodles (same `#cam` blur + dim mechanism).

## Method

- Full-frame: exactly `scripts/render.sh` per chunk (`HF_CAPTURE_PARALLEL_STREAM=true`, `--resolution 4k --fps
  60 --video-bitrate 60M --gpu --browser-gpu`, own `--frames-cache-dir`).
- Overlay: `build_overlay.py` splits each chunk into two layers: `behind` (clips inside `#cam`, under the
  cut-out) and `front` (everything else + the `#fade` div). Cue windows merge when closer than 1 s, get one
  transparent pad frame at the end, and are **packed back to back** into one composition per layer, so each
  layer is one HyperFrames run and Chrome never opens a frame without a graphic. `composite.py` maps packed
  frames back to real time (`setpts` on frame number) and builds the chunk in ffmpeg:
  program (VT decode) → punch-in (crop + scale) → blur + dim (quarter-res gblur σ10, ×0.42, eased alpha) →
  behind → cut-out (VP9 alpha) → front (incl. fade) → `h264_videotoolbox` 60M; SFX mixed with `amix`.
  The chunk is cut at every event boundary into ≤10 s segments run 4 at a time, joined with concat copy.
- Same machine (M1 Pro, 16 GB), back to back (`scripts/runall.sh`). **The machine was shared**: other agents
  (rustc, svelte-check, Studio transcription, a pytest run) pushed the load average to 5–98 during the day.
  Load at the start of the clean run: 5 (full-frame), 18 (overlay). The composite runs under `nice -n 19`
  (hook rule) while HyperFrames' own ffmpeg does not, so contention hurt the overlay path more.

## Numbers (clean back-to-back run)

| | full-frame chunk-00 | overlay chunk-00 | full-frame chunk-05 | overlay chunk-05 |
|---|---|---|---|---|
| Chrome frames | 8994 | 4853 (308 behind + 4545 front) | 2562 | 1390 |
| Chrome render wall | 707 s (extract 184 + capture 509) | 39 + 208 s | 203 s | 96 s |
| ffmpeg composite wall | — | 385 s | — | 54 s |
| **total wall** | **707 s** | **632 s** | **203 s** | **150 s** |
| peak scratch disk | 3.2 GB frame cache | ~2.2 GB HF work dir during capture; PNGs 1.06 GB; segments 0.45 GB | 0.56 GB | PNGs 0.31 GB |
| output size | 896 MB | 450 MB | 289 MB | 161 MB |

Both chunks: full-frame 910 s, overlay 782 s → **1.16× faster**. An earlier quieter full-frame run took
575 + 179 s = 754 s (the Telegram project's own log: 9:08 + 2:44), which would make the two paths about even.

Where the overlay time goes:
- Chrome alpha capture is cheap: 4545 frames in 188 s (24 fps, 3 workers) vs 17.7 fps full-frame capture,
  and no 3-minute video frame extract. Chrome work fell from 910 s to 343 s.
- The composite is the new cost. Alone, one doodle-over-blur segment composites at 26 fps (33 fps without
  the encode; decode + VT encode alone 39 fps); four in parallel on the loaded machine fell to 2.4 fps each.
  Aggregate: 24 fps for chunk-00, 51 fps for chunk-05. The VT encoder (one engine) and CPU overlays at 4K
  set the ceiling; every frame of the chunk is still decoded, composited and re-encoded.
- Output is smaller because `h264_videotoolbox -b:v 60M` undershoots on short segments (~24 vs 48 Mbps);
  quality is still equal (below). A real build would fix the rate (`-q:v` or constant bitrate) per segment.

## Transparent output (found in hyperframes@0.8.170 source, not guessed)

- `--format mov` → ProRes 4444 `yuva444p12le` via **`prores_ks` (CPU)**; `--format webm` → VP9 `yuva420p`
  via `libvpx-vp9` (CPU); `--format png-sequence` → RGBA PNG frames, no encode. Alpha capture is
  `Page.captureScreenshot` PNG with a transparent default background; at DPR 2 (4K) fast capture is off.
- Streaming capture: multi-worker streaming is only for mp4/hls (`shouldStreamParallelCapture`). Alpha output
  either streams with `--workers 1` (6.3 fps at 4K) or goes to multi-worker disk capture. `HF_SEGMENTED_CAPTURE`
  for mov fails (it writes an mp4 container).
- Disk-capture preflight assumes raw RGBA (33 MB/frame at 4K) even for PNG: a 4545-frame render "needs
  151 GB" and is refused on a 40 GB-free disk, though the real frames average 0.23 MB. The spike passed
  `scripts/statfs-shim.cjs` (reports 8× free space; real use measured) — **needs an upstream fix** (estimate
  PNG from measured frames) or vedit must keep each alpha render under ~1000 frames (a window can't be split:
  a negative `data-start` renders nothing).
- Measured for the same 308-frame layer: ProRes via HF 44–90 s (encode after capture, `prores_ks` 5–10 fps),
  ProRes `--workers 1` 50 s, **PNG sequence 13 s** (74 MB).

VideoToolbox, tested with ffmpeg 7.1.1:

| intermediate | VT decode keeps alpha | VT encode with alpha | notes |
|---|---|---|---|
| ProRes 4444 | yes (`ayuv64le`, 148 fps vs 76 CPU) | yes (`prores_videotoolbox -profile:v 4444`, 14 fps) | HF itself only writes it with `prores_ks` |
| HEVC + alpha | **no** (alpha dropped, CPU and VT) | yes (`hevc_videotoolbox -alpha_quality`) | unusable in ffmpeg |
| VP9 alpha | no VT path | no VT path | CPU only (`libvpx-vp9`), as the traps say |
| PNG frames | n/a (CPU decode, ~210 fps at 4K) | n/a | no encode at all |

**Chosen intermediate: PNG frames** (`--format png-sequence`), CPU-decoded in the composite. If the overlay
must be kept between runs, transcode it once to ProRes 4444 with `prores_videotoolbox` (VT decodes it with
alpha).

## Visual check

`out/contact-sheet.png` (full-frame | overlay | diff ×4 at the 6 peaks) and `out/contact-crops.png` (2× crops).
PSNR / SSIM full-frame vs overlay: big word 45.9 dB / 0.989, punch-in 40.2 / 0.995, chapter card 40.4 / 0.982,
doodle 39.2 / 0.982, full-screen scene 42.4 / 0.976, end fade 48.8 / 0.968. The diff shows codec noise and a
slightly different blur kernel only; text edges over transparency (crops 1, 4, 5) show no fringe or halo.
Crops 2, 3 and 6 landed beside the text and don't test edges.

Bugs found and fixed on the way: blend opacity driven by `sendcmd` did not apply in segments that start
mid-blur (the doodles came out sharp); replaced by a 16×10 `geq` mask + `alphamerge`. A per-pixel `geq`
alpha at 4K ran at 4 fps.

Differences that remain by design: the blur ramp is a crossfade (brightness matches exactly, radius does not
grow) over 0.3–0.35 s; the cut-out start may be 1 frame off; punch-in zoom and blur are applied to the program
only, so a big word during a zoom or a blur would need the same transform (none in this sample; a real build
must assert it or apply it).

## Decision

**Not adopted for now.** Output is equal, Chrome work drops by 62 %, but the whole chunk is 1.16× faster
on this run and about even against the quiet baseline: not clearly faster. Full-frame stays the render path.

What would make overlay a clear win (each measurable on the same fixture):
1. Bake punch-ins into the program pass (`tools/program.py` already re-encodes the whole program on VT) and
   force keyframes at cue-window edges; then stretches without graphics or blur are **stream-copied**, and the
   composite decodes and encodes only the ~50 % of frames that carry a graphic.
2. HyperFrames: a PNG-aware disk estimate (or multi-worker streaming for alpha) so no shim is needed.
3. Blur regions rendered at program time too (they are deterministic), leaving the composite as overlays only.

## Impact on other leaves

- `feature-compose.md`: overlay mode stays optional; if it comes back, its layer split, window packing (pad
  frame, 1 s merge) and the `.vedit/composite.json` plan are prototyped in `build_overlay.py`.
- `feature-render.md`: full-frame remains the default; nothing to change now. Free-disk check must count the
  frame cache (3.2 GB per 150 s chunk measured) plus HyperFrames' work dir.
- `feature-draft.md`: draft keeps the full-frame path at 1080p.
- `feature-program` (wherever punch-ins move): idea 1 above needs zoom keyframes in the program step.
