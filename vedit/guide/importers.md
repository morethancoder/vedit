---
summary: any video in; importer plugins for recorder projects; your defaults live in config
next: vedit importers
---
# Importers: any recorder, your workflow

vedit takes any video file: `vedit new talk.mp4`. Nothing more is needed.

Some recorders also keep the camera on its own (no overlays, zooms or backgrounds) and save the edit as a list
of trims. An **importer** is a small Python file of yours that reads such a project, so vedit can use the clean
camera instead of the flattened export. vedit ships none; importers live in your config, not in vedit:

```
~/.config/vedit/importers/<name>.py     ($VEDIT_CONFIG_DIR replaces ~/.config/vedit)
$VEDIT_IMPORTERS                        more folders, ':'-separated
```

Files starting with `_` or `test_` are skipped (keep your tests next to the plugin). Plugins are tried in file
name order and the first that recognises a path wins. `vedit importers` lists them; `vedit importers PATH` says
which one reads PATH.

## The interface

```python
"""One line: what this importer reads."""  # shown by `vedit importers`

from pathlib import Path
from vedit.recording import Camera, Recording, RecordingError, Trim

NAME = "myrec"  # optional; default: the file name


def read(path: Path) -> Recording | None:
    # None: not mine. Raise RecordingError: mine, but broken (the message reaches the user).
    return Recording(
        video=path / "export.mp4",  # the edited video: its audio and timing are used
        name="My talk",  # project folder name base
        camera=Camera(  # optional: clean camera behind the edit
            tracks=[path / "camera-0.mov"],  # one file per track, index 0..n-1
            trims=[Trim(0, 1.5, 62.0), Trim(0, 70.2, 180.4)],  # kept stretches, end to end = the edit
            fps=30,
            mirror=False,
        ),
        origin=path,  # the recorder project (for `vedit clean --posted`)
    )


def originals(origin: Path):  # optional, for `vedit clean --posted`
    return [(origin, "recorder project")], []  # (delete with why, kept paths)
```

The camera trims must add up to the edited video's length: vedit lays them end to end with the video's audio
(`.vedit/media/<A>-cam.mp4`), so a mismatch shows as drift.

## What `vedit new` writes

```yaml
sources:
  A:
    file: src/A.mp4            # the edited video (link to the original)
    camera: src/A-camera.mov   # or a list, one per track
    trims: [[0, 1.5, 62.0], [0, 70.2, 180.4]]   # [track, start, end] seconds
    fps: 30
    mirror: false
    origin: /path/to/recorder/project
    importer: myrec
    punch: true                # optional: punch-ins on jump cuts (default: on for camera sources)
```

You can write this by hand too, with no importer: `camera` without `trims` uses the camera whole, without `fps`
its own frame rate.

## Your other defaults

Personal choices live in config, never in vedit: `~/.config/vedit/config.yaml` (`channel:`, `style:`,
`projects:` the folder new projects go in), channels (`vedit guide channels`), your own style packs
(`vedit guide styles`) and logos (`~/.config/vedit/logos/`, or a channel's `logos/`).
