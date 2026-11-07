# Pipeline: what each stage must do

Moved from the `youtube-edit` skill (steps 1–11). These are settled decisions: encode them as defaults.

## new: ingest
- ffprobe every source; one contact sheet per source.
- **Camera sources** (`camera:` + `trims:`, usually from an importer plugin): the clean camera laid on the trims,
  with the edited video's audio. Frame counts per trim come from the cumulative edit clock (no drift). A
  recorder's export may be cropped, pause-trimmed or mirrored; the clean camera is not. Source:
  `tele-a7/scripts/source.sh`.
- 1080p30 VideoToolbox proxies of every source; 48 kHz stereo WAV of the audio.

## transcribe
- Studio only. Arabic: `--model qwen3-asr-1.7b --lang ar --dialect iq --fillers keep`, word times on.
  English: Studio's best English model. Names from `project.yaml hint` go in `--hint`.
- Cache by source hash. Store words in source time `[{clip, t0, t1, w}]`.

## cut
- Three kinds of cut: phrases (cuts.yaml), standalone fillers, pauses > 0.5 s shortened to 0.3 s.
- Boundaries snap to the quietest 10 ms within 0.12 s; ranges quantised to 1/30 s so proxy (30 fps) and master
  (60 fps) cut on the same frames.
- **Refine by listening:** ASR word times drift up to ~0.5 s. For each cut, try K=3 quiet points per side
  (9 splices), put every splice (1.6 s context each side, 2 s gaps) in one WAV, transcribe it in one Studio pass,
  keep the splice that reads "words before + words after" without the removed words. Cache by cut.
- Audio joins: 60 ms equal-power crossfades with handles, never fades to zero (they dip and sound like glitches).
- Chapter holds: 1.8 s held frame, **true digital silence, no sound effect**, under a full-screen chapter card.
- End: fade to black starting as the last word ends (fast-darkening ease) over running footage. Never freeze.
- Camera-to-camera jump cuts alternate a 1.07× punch-in; screen layouts never zoom.
- Program render: each run of pieces from one source is one GPU-decoded `select` pass, VideoToolbox encode.
  **New:** render per piece and concatenate, so a changed cut re-renders seconds, not the whole film.

## joins
- Transcribe the cut program; for every join print the ~2.2 s of words before ‖ after.
- **New:** compare with the expected words (source transcript minus the cut) and print only the joins that
  differ: clipped or garbled words, dropped words that change meaning. A natural repeat beats a broken word:
  the fix is to drop the cut or pin it.
- When the cut changes, regenerate in this order: refine → edl → program → joins → build → cut-outs → review.

## faces
- Face box per sample at 4 fps on the proxy (OpenCV Haar frontal face, largest face), index rows by real
  spacing. `cam` = face low and large (centre y > 260 of 1080, w > 170); the bubble face is at the top.

## build (graphics engine)
- Anchor each cue by its spoken words → program time via the edl.
- **Fit in shot:** every label/chip/kinetic/big word sits inside one continuous shot (no cut, layout switch or
  full-screen scene inside its window); trim or move it.
- **Never on his face:** side chosen per cue from the face track over its whole window (margin 40 px).
- Theme (light/dark text) from the measured brightness of the frame behind the graphic. No boxes behind text:
  contrast comes from layered text shadows; over busy screens a feathered backdrop blur (no tint).
- `backdrop-filter` dies inside any ancestor with opacity < 1: blur element beside the text, faded on its own.
- Big words: person cut-out over the word, at most one letter tucked behind the head, shelf removed from the matte.
- Doodles: full screen over the blurred + dimmed A-roll; blur (0.3 s) and first stroke start together; elements
  draw on their words; end ~2.5 s after the last element; back-to-back full-screen scenes overlap and crossfade.
- SFX ~18 dB under the voice (program ≈ −16 LUFS): soft click, pop, short whoosh, key press. No sparkles/bells.
- Then `hyperframes lint` + `check`; every `<audio>` has `data-duration`.

## review
- Snapshot every graphic at its peak; one contact sheet. **New:** flag text overlapping the face box, text under
  a minimum size, low contrast, doodles still drawing at fade-out. Opus still looks at the sheets.

## draft
- 1080p draft render, opened with `open -a "QuickTime Player"`. Never a Studio preview.
- Rendered per chunk (`-c chunks/chunk-NN.html`, the 4K master's cuts), 2 at a time, each keyed and kept in
  `.vedit/renders/draft-parts/`; joined losslessly (audio re-encoded once). A rerun renders only changed chunks.
- Measured on the Telegram film (13:08, M1 Pro 16 GB, 2026-11-06): **1528 s → 768 s → 411 s**.
  - Fast capture off (`--experimental-fast-capture=false`, now on every render): our compositions use `filter:
    blur`, which drawElementImage can't draw, so HyperFrames falls back to screenshots; but for ≥ 900 frames it
    first picks *single-worker* fast capture and keeps that one worker after the fallback. A 150 s chunk at
    1080p: 322 s → 145 s.
  - Chunks, not the whole film: a frame of the full composition (48 graphics loaded) captured 1.7× slower than
    the same frame from its chunk (9 graphics): 20.9 vs 12.2 s for the same 14 s.
  - 2 chunks at once: 1.67× throughput at 1080p (3 at once: 1.78×). At 4K only 1.18×: the GPU and encoder are
    the limit there, so the master stays one chunk at a time.
  - No effect: `--workers 6` (same as auto's 3 at both sizes); a native 3840×2160 composition (fast capture
    still off because of the blur, same time).

## subs
- Cues from the program transcription: ≤ 84 chars, ≤ 6 s, split on gaps ≥ 0.6 s.
- Cleanup + translation per cue via the router (batches of 40, ids must round-trip).
- Arabic SRT: U+200F per line, U+200E before tokens starting with a symbol (`.env`, `--flag`); Latin kept for
  product names and commands. No burned-in captions.

## render (4K60 master)
- **Full-frame is the render path.** Overlay-only (Chrome renders only the graphics, transparent, only in cue
  windows; ffmpeg composites program → zooms → blur → behind → cut-out → front) was measured on 192.6 s of the
  Telegram film (chunks 00 + 05, M1 Pro, shared machine, back to back) and **not adopted**: equal output
  (PSNR 39–49 dB at the 6 peaks, no fringe), but only 1.16× faster.

  | | full-frame | overlay |
  |---|---|---|
  | wall (chunk-00 + chunk-05) | 707 + 203 = 910 s | (39 + 208 + 385) + (96 + 54) = 782 s |
  | frames through Chrome | 11 556 | 6 243 (Chrome time 910 → 343 s) |
  | peak scratch disk (chunk-00) | 3.2 GB frame cache | ~2.2 GB capture work dir, 1.06 GB PNGs |
  | output size (chunk-00) | 896 MB | 450 MB (VT undershoots on short segments) |

  Alpha intermediate: **PNG frames** (`--format png-sequence`): HyperFrames' ProRes 4444 is `prores_ks` on
  the CPU (5–10 fps at 4K), VP9 alpha is CPU only, HEVC alpha loses its alpha on decode. VT decodes and encodes
  ProRes 4444 with alpha, so cache overlays as `prores_videotoolbox` if needed. The cost moved into the
  composite (every frame still decoded, composited, re-encoded). Clear win needs punch-ins baked into the
  program pass and stream copy outside graphic windows. Details: `plans/phase-04-graphics/spike-results.md`.
  Why not a native (Rust/Go) renderer: the TypeScript part of HyperFrames is thin glue; the time is Chrome
  painting 4K frames and reading them back. Replacing Chrome would mean our own text/RTL/SVG/animation engine
  and losing HTML/GSAP, which agents write well.
- Full-frame (measured):
- 4K program + 4K cut-outs first, then the film in ~150 s chunks cut where only the A-roll is on screen.
- Each chunk: `HF_CAPTURE_PARALLEL_STREAM=true`, `--resolution 4k --fps 60 --video-bitrate 60M --gpu --browser-gpu`,
  its own `--frames-cache-dir`, deleted afterwards. Finished chunks are kept so a rerun resumes.
- Join video losslessly; audio from each chunk's PCM in one AAC 320k pass; `+faststart`; verify frames = duration × 60.
- Disk: a full-film render at once needs ~50 GB of frames; multi-worker disk capture ~75 GB per chunk; the
  streamed 150 s chunk's frame cache peaked at 3.2 GB (2026-11-05).
- Measured: 13-min film ≈ 85 min (4K program ≈ 25, cut-outs ≈ 30, 6 chunks ≈ 9 each) on an M1 Pro; a 150 s
  chunk is 9:08–11:44 depending on machine load (3 min frame extract + 8994 frames captured at 15–18 fps).
- Measured with `vedit render` on the fixture (2026-11-05): 4K program 15 min (160 pieces, 4 at a time), cut-outs
  12 min (2), 6 chunks 47 min (8–9.5 min per full chunk), join 53 s: ≈ 76 min, master 4.98 GB, 47422 frames.
  A rerun after one chunk's composition changed: that chunk only (8.6 min) + join.
- Frame exactness: a camera's audio can outlast its video (fixture: 928.44 vs 928.36 s), so a program piece that
  runs past the video end holds its last frame; HyperFrames renders ceil(duration × fps) frames, so chunk
  durations are written just under the frame (`compose.frame_safe`), else a chunk gains a frame and the picture
  falls behind the sound for the rest of the master.

## clean
- Always: frame caches, render chunks, scratch audio/video in `.vedit/`.
- `--posted` (after the upload is confirmed): renders, proxies, program, cut-outs, and the originals behind `src/`:
  plain source files, and for importer sources the recorder project (the importer's `originals()` may add
  twins and name exports to keep; exports are often APFS clones that free nothing).
  Keep cuts.yaml, cues.yaml, custom/, youtube/, subs, transcripts. Report GB freed.
