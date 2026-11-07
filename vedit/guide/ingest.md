---
summary: start a project (vedit new), then transcribe it
next: vedit transcribe
---
# Ingest

## vedit new

```
vedit new <input>... [--slug S] [--lang ar|en] [--dialect iq] [--style S] [--channel H] [--hint TEXT] [--dir PARENT]
```

`<input>` is a `.cap` folder, a Cap export (matched to its `.cap`), or one or more plain video files (sources
A, B, C...). The project goes in `<PARENT>/<slug>/` (`~/Demos` by default); never inside a git repo.

It writes:

- `project.yaml`: slug, lang, dialect, channel, hint, sources. `style` and `accent` are written only when you
  pass them; otherwise they come from the channel, then `~/.config/vedit/config.yaml`, at run time.
- `src/`: symlinks to the originals (Cap: `A.mp4` export, `A-camera.mp4` raw camera). Originals are never touched.
- `cuts.yaml`, `cues.yaml`: empty templates with commented examples. `custom/`: for your own HTML.
- `.vedit/media/`: `A-cam.mp4` (Cap only: raw camera on Cap's trims with the export audio, mirrored when Cap
  mirrors), `proxy/<clip>.mp4` (1080p30), `<clip>-48k.wav` (48 kHz stereo), `sheet/<clip>.jpg` (4x4 contact sheet).

Language: `--lang` or the channel's `lang` is required. Unpassed lang, dialect and hint come from the channel
(`vedit guide channels`). `--channel` defaults to config.yaml's `channel`.

Rerun the same command any time: finished outputs are skipped by content hash (source path, size, settings),
missing ones are made, project.yaml is kept (a warning shows flags that differ; edit the file by hand).

Look at `.vedit/media/sheet/A.jpg` to see what the recording holds. Log: `.vedit/logs/new.log`.

## vedit transcribe

```
vedit transcribe [--wait] [--clip A] [--force]
```

Word-timed transcript of every source clip, from `.vedit/media/<clip>-48k.wav`, through Studio (fillers kept).
Arabic uses qwen3-asr-1.7b with the project's `dialect` and `hint`; English passes `--lang en` and leaves the
model to Studio (`auto` picks its English model).

It writes `.vedit/words/<clip>.json` (`[{t0, t1, w}]`, source seconds) and `<clip>.txt`: one line per phrase,
`MM:SS.ss-MM:SS.ss  words`. Read the `.txt`; the cuts refer to times in it.

By default it runs detached (log `.vedit/logs/transcribe.log`) and returns at once; watch it with
`vedit status` (shows `clip i/n`). `--wait` works in the foreground. A second job is never started while one
runs. Reruns are instant: a clip is skipped when its words exist and the wav and settings are unchanged
(Studio's own cache also hits); `--force` redoes it. Next: `vedit summarize`.

Tokens mixing Arabic and Latin letters (ASR glitches such as `سalam`) are listed as a warning per clip, with times; `--json` carries them as `mixed_script: [{t, w}]` per clip.
