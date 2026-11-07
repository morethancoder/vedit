---
summary: pick a style pack; where packs live, which one wins, what a pack folder holds
next: vedit styles
---
# Style packs

A style pack decides how every cue type looks. Cue files never change when the look changes.

## Find and list

- `vedit styles` lists every pack: name, scope (`built-in`, `global`, `channel:<handle>`), summary, its own types
  and inherited ones, plus any pack problems. `--channel <handle>` adds that channel's own packs (inside a
  project the project's channel is used). `--json` gives the same as one value.
- `vedit styles find "warm doodle arabic"` ranks packs by words: each query word counts 3 when it is one of a
  pack's `keywords:` and 1 when it is in its `summary:` or name (case, accents, plurals and -ing/-ed ignored).
  No model; it prints the top matches with their scores.
- `vedit styles show <name>` prints the accent and colours, fonts, language, own vs inherited types, the pack's
  path and the path of its specimen sheet (`vedit style try <name>` makes it) when one exists.

## Built-in packs

- `base`: the neutral fallback every pack extends: every type, ivory text, a grey accent, no hand lettering.
- `yellow-doodle`: the Telegram video: yellow accent, Ruqaa hand lettering, spinning spark, Arabic.
- `claude-violet`: violet accent, Source Serif titles, English (Arabic capable).

## Where packs live (nearest wins)

```
~/.config/vedit/channels/<handle>/styles/<name>/   channel-only packs (the project's channel)
~/.config/vedit/styles/<name>/                     global packs ($VEDIT_CONFIG_DIR replaces ~/.config/vedit)
vedit/styles/<name>/                               built-in
```

The first folder holding `<name>/pack.yaml` wins, so a channel pack named `yellow-doodle` replaces the
built-in one for that channel. `drafts/` under the global styles holds packs being authored; it is never a
pack name. A name that resolves nowhere is an error that lists the places searched.

## Which style a cue uses (first set wins)

cue `style:`, then cues.yaml `style:`, then project.yaml `style:`, then the channel default (`vedit channel
add <handle> --style <name>`), then the global default (`style:` in `~/.config/vedit/config.yaml`), then
`base`. `vedit status` prints the one that applies and where it came from, for example
`style yellow-doodle (from channel ali)`. To switch a video, change that one line; nothing else.

## Pack folder

```
pack.yaml          tokens (below)
fonts/             font files named in pack.yaml `fonts:`
logos/*.svg        marks cues can name (`logo: spark`)
sfx/*.mp3          sounds named in `sfx:`
types/<type>.html  one template per cue type: slot header, <style>, body, <script>
partials/*.html    shared fragments, pulled in as {{&part.<name>}}
```

A type missing from a pack comes from its `extends:` pack, then from `base`. So a new pack can be just a
`pack.yaml` with new colours and motion, and add `types/` files only where the layout differs.

`pack.yaml` keys: `name`, `extends`, `summary` (one line), `keywords` (words someone would search: look, mood, language), `lang`, `colors`, `fonts`, `font`, `themes`
(`dark` and `light`: `text`, `sub`, `kicker`, `shadow`, ...), `busy_shadow`, `motion`, `advances`, `big`,
`logo_motion`, `focus`, `sfx`, `sfx_files`. Any other key is reported as a problem.

`motion:` tokens: `ease_in`, `ease_out`, `ease_draw`, `ease_pop` (GSAP ease names), `in`, `out`, `out_lead`,
`scene_out`, `scene_lead`, `stagger` (seconds), `rise` (px).

## Templates

A mustache subset: `{{x}}` escaped, `{{&x}}` raw, `{{#x}}..{{/x}}` (list: per item; truthy: once),
`{{^x}}..{{/x}}` (falsy), dotted names, `{{.}}` the current item. The header comment declares the slots:

```
<!-- vedit
slots:
  title: {required: true, help: "the main line"}
  logo: {kind: logo}
-->
```

Slot kinds: text, bool, number, list, words, beats, logo, file. A cue field that is not a slot is an error.
Context every template gets: `id`, `type`, `dur`, `side`, `left`, `right`, `dir`, `theme`, `th.*` (theme
colours and shadow), `c.*` (colours), `font.*`, `m.*` (motion), `logo.html`, `logo.spin`, `part.*`, `blur`,
and the cue's slots by name. Scripts get `tl`, `D` (duration), `q`/`qa` (query inside the graphic).

## Checks

`vedit styles` and `vedit build` check a pack all at once: unknown pack.yaml keys (with the closest key),
missing font/sfx/advances files, unknown logo names, templates whose header or sections do not parse, bad slot
kinds. `vedit build` stops on a pack with problems and lists them.

No pack fits: `vedit guide style-authoring`.
