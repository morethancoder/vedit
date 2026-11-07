# Studio: the home of all local AI

The creator's rule: **every local AI model run happens in Studio** (`studio` CLI → app server at 127.0.0.1:8799, repo
`~/Projects/New/studio`, docs `docs/CLI.md`). vedit never bundles a model. If vedit needs a capability Studio lacks,
the capability is added to Studio first. Plain signal processing and classic computer vision (silence detection,
loudness, OpenCV Haar faces, frame brightness) are code, not models, and stay in vedit.

All calls use `studio --json …`; Studio starts its server on demand and stops 30 s after the work.

## Already there

| vedit needs | Studio command | Notes |
|---|---|---|
| Transcription with word times | `studio transcribe FILE --lang ar --dialect iq --fillers keep --no-vad -o out.json` | qwen3-asr-1.7b, free, ~80 s per 15-min pass; verbatim Iraqi. whisper-large-v3-turbo also available for English. |
| Listening probes (refine, joins) | same, on a spliced WAV | one pass per batch of splices |
| Still cut-outs (thumbnails) | `studio cutout IMG --model birefnet --out x.png` | replaces most of `still_mask.py`; shelf cleanup may still be needed |
| Video cut-outs (big words) | `studio --json cutout VIDEO --start S --duration S --model birefnet-lite --out x.webm` | largest person only (no shelf), VP9 alpha; ~0.76 s/frame at 1080p on M1 Pro (5 s clip ≈ 2 min). Support detected from `studio cutout --help`; without it vedit falls back and `vedit doctor` warns |
| Speech model check | `studio --json models --speech` | `vedit doctor` reads qwen3-asr-1.7b `downloaded`/`loadable` here |
| Judgments / ranking | `studio judge … --engine kev` (local) or `jev` (TypeSafe cloud) | later: rank proposed cuts "is this real filler?", review flags |
| Upscale stills | `studio upscale` | thumbnails |

## Must be added to Studio (phase 06)

1. **Video cut-out** (shipped on Studio branch `vedit/video-cutout`, wired 2026-11-05): `studio cutout VIDEO.mp4 --out matte.webm` (or ProRes 4444) → per-frame person matte with
   temporal smoothing, alpha video out. Today vedit's big words use `hyperframes remove-background` (a local
   model outside Studio) plus `matte_mask.py` to drop the bookshelf. Needs: birefnet(-lite) per frame or a video
   matting model, a subject-only option (largest person / face-anchored) so the shelf mask hack goes away.
   *Fallback for an older Studio:* `hyperframes remove-background` + `matte_mask.py`, marked `# TEMP(studio-cutout)`;
   drop it once every machine runs the new Studio.
2. **Batch transcription of many short clips in one job** (optional): refine/probe currently splice into one WAV
   to save model loads. A `studio transcribe --batch a.wav b.wav …` keeping per-file times would simplify refine.
3. **Local text model** (optional, later): only if the creator wants summaries/subtitles fully offline. Today those use
   cloud models through vedit's router (docs/models.md).

## How vedit talks to Studio

- One module (`vedit/studio.py`): build the command, run with timeout, parse JSON, surface Studio's stderr
  warnings (missing aligner, estimated times) in the report.
- Cache every result by input hash + options under `.vedit/studio/`.
- `vedit doctor` checks `studio status --json`: server reachable, qwen3-asr downloaded, aligner present.
