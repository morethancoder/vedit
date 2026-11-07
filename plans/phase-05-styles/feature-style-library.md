# Style library: global, per channel, keywords

Styles are picked by name or by words, and each YouTube channel has its own set and default.

Done when:
- [x] packs resolve from three places, nearest wins: channel (`~/.config/vedit/channels/<handle>/styles/`) → global (`~/.config/vedit/styles/`) → built-in (`vedit/styles/`)
- [x] `channel.yaml` per channel holds its default style, language, accent, logos; `vedit channel add <handle>` / `vedit channel show` manage it
- [x] style used = cue `style:` → cues.yaml `style:` → project.yaml `style:` → channel default → global default (`~/.config/vedit/config.yaml`); `vedit status` shows which one won and why
- [x] `pack.yaml` carries `keywords:` and a one-line `summary:`; `vedit styles [--channel x]` lists name, scope, summary; `vedit styles find "warm doodle arabic"` ranks by keyword overlap (plain code, no model)
- [x] `vedit styles show <name>` prints tokens in a few lines plus the path of its specimen sheet; `guide styles` and `guide channels` written

## Approach

Keyword match is rule-based: normalise, stem lightly, score overlap with keywords + summary. A later Jev
ranking is only worth it if keywords fail in practice (after v1).

## Refs

- depends on: [`feature-pack-format.md`](feature-pack-format.md)
- [`../phase-02-ingest/feature-new.md`](../phase-02-ingest/feature-new.md) (`--channel`)
