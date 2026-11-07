# Project file and paths

Load and validate `project.yaml`, find the project from any subfolder, and give every module one place for paths.

Done when:
- [x] `project.yaml` per docs/formats.md loads with clear errors for unknown keys and missing sources
- [x] `Project.paths` covers src/, cuts.yaml, cues.yaml, custom/, and every `.vedit/` subfolder (studio, words, edl, program, mattes, hf, renders, logs)
- [x] commands run from inside a project folder find it by walking up; `--project PATH` overrides

## Approach

A dataclass for the config, defaults filled in (pauses, fillers, style). No video-specific constant survives
in code: durations come from ffprobe, clips from `sources`.
