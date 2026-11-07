---
summary: per-channel defaults: style, language, accent, logos; channel packs and plug
next: vedit channel show
---
# Channels

A channel is one YouTube channel's defaults. They live in `~/.config/vedit/channels/<handle>/`
(`$VEDIT_CONFIG_DIR` replaces `~/.config/vedit`):

```
channel.yaml        style, lang, dialect, accent, logos, hint
styles/<name>/      packs only this channel sees (win over global and built-in)
plug/plug.yaml      plug preset for this channel (+ the files it names)
```

## Commands

- `vedit channel add <handle> --style yellow-doodle --lang ar --accent '#FFD60A'` creates the channel, or
  changes only the flags you pass on an existing one. Flags: `--style`, `--lang`, `--dialect`, `--accent`
  (a hex colour), `--logos telegram,octopus`, `--hint`. A `--style` that does not resolve for the channel is an
  error naming the places searched.
- `vedit channel show <handle>` prints its defaults, its own packs and its plug preset. Without a handle it
  shows the default channel (`channel:` in config.yaml), or lists every channel.
- `vedit styles --channel <handle>` lists the packs that channel sees; `vedit styles find` and `show` take the
  same flag.

## How a project uses it

- `vedit new <input> --channel <handle>` saves `channel:` in project.yaml; without the flag, config.yaml's
  `channel` is used. `new` fills lang, dialect and hint from channel.yaml when you pass none.
- Style and accent resolve at build time (project.yaml, then channel, then config.yaml), so a later channel
  change still applies. The full style order is in `vedit guide styles`; `vedit status` shows which one won.
- Pack names resolve channel, then global, then built-in, using the project's channel.
- Plug: the project's `custom/plug/plug.yaml` wins; without it the channel's `plug/plug.yaml` is used (see
  `vedit guide cue-plug`). One replaces the other whole, files included.
