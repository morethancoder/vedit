# vedit new

Create a project folder that's ready to transcribe.

Done when:
- [x] creates `~/Demos/<slug>/` with project.yaml, src/ links, empty cuts.yaml / cues.yaml templates, custom/
- [x] builds `.vedit/media/A-cam.mp4` (clean camera on its trims + export audio), 1080p30 VideoToolbox proxies, 48 kHz WAV, one contact sheet per source
- [x] rerunning skips finished work; plain video files work too
- [x] `--channel <handle>` (default from `~/.config/vedit/config.yaml`) is saved in project.yaml; the channel's default style, language and accent fill in what wasn't passed

## Approach

Port T `scripts/source.sh` + `media.sh` proxy half. Slug from `--slug` or the export name. Never inside a code repo.

## Refs

- depends on: [`feature-recorder-reader.md`](feature-recorder-reader.md)
