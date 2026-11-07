---
summary: hand-drawn scene whose elements are drawn on spoken words; library scenes or an inline spec
next: vedit doodle preview <scene>
---
# cue type: doodle

A hand-drawn explainer over the blurred footage: each beat's shapes are drawn with a pen stroke, and its
hand-lettered labels written on, when the beat's words are spoken. Line colours, weight, wobble and lettering
come from the style's `doodle.yaml`; the scene only says what is drawn where.

## Write (library scene)

```yaml
- type: doodle
  at: "words that start it"
  scene: flood                 # a library scene (below), or an inline spec
  beats:                       # beat -> the words that draw it
    bot: "words for the bot"
    flood: "words for the flood"
```

## Library scenes

Run `vedit doodle list` for every scene with its beats. Arabic scenes (Telegram video): `path` (civil, code,
freelance, skills), `request` (group, msg, telebot, question), `dms` (phone, bubbles, business, creators,
paid), `flood` (bot, flood, second, crash), `funnel` (post, followers, platforms, telegram, crash), `chart`
(tools, start, end, years), `gate` (tiktok, bot, free, check, no, grow), `broadcast` (bot, users, broadcast,
dm, better), `experience` (load, many, stats, broadcast), `nativeapp` (tg, miniapp, bot, host, ai,
templates), `mcp` (apps, connect, build, publish), `login` (login, code, noshare, trust, permit, build).
English scenes (Claude Code in Telegram): `remote`, `pairing`, `alwayson`, `botapi`, `chatid`, `bot`,
`harness`. A library scene's labels are fixed text; for other words write an inline spec.

## Write (inline spec, short form)

```yaml
- type: doodle
  at: "البوت عليه ضغط"
  scene:
    layout: row                # row (right to left for Arabic) | column; elements without `at` spread out
    elements:
      - {beat: bot, id: bot, bot: {}, label: "البوت"}
      - {beat: mail, id: mail, envelope: {w: 120}, label: "رسائل"}
      - {beat: mail, arrow: {from: mail, to: bot}, label: "آلاف"}   # arrow edge to edge, by id
      - {beat: crash, text: "طاح!", at: [500, 880], color: warn}
  beats:
    bot: "البوت عليه ضغط"
    mail: "آلاف الرسائل"
    crash: "طاح"
```

Element keys: `beat` (required), one shape, `id`, `at: [x, y]` (centre, px on 1920x1080), `label`, `size`,
`color`, `pen` (seconds the stroke takes), `after` (seconds after the beat), `float`. A `text` element needs
`at`. Shapes take their defaults when given `{}`.

## Write (inline spec, full form: what the library uses)

```yaml
  scene:
    beats:                      # beat -> steps, in drawing order
      bot:
        - pen: 1.0              # one pen pass: draws its shapes in 1.0 s
          float: 4              # px idle float once drawn
          shapes:
            - bot: {at: [500, 570], w: 240, h: 210}
            - arrow: {a: [1200, 440], b: [760, 440], size: 18, lw: 0.8}
        - {text: "البوت", at: [500, 790], after: 0.6, size: 64}
```

Step keys: a pass has `pen` (seconds, or `next` to join the next pass), `shapes`, `after`, `float`, `name`,
`into` (add to an earlier named pass), `spin: {about: [x, y], rate, after, of}`. A text has `text`, `at`,
`after`, `size`, `weight`, `color`, `mono`, `anchor` (middle, start, end).

Shapes: icons `bot` (w, h, face: eyes|spark|null), `laptop` (w, prompt, fill), `phone` / `play_phone` (w,
h), `server` (w, units), `rack`, `person` (size, fill), `people` (size), `bubble` (top-left at, w, h, side),
`window` (top-left at, w, h), `megaphone` (size), `key` (size), `clock`, `gear`, `coin`, `stopwatch`,
`gauge`, `telegram` (R), `envelope`, `shop`, `gift`, `hardhat` (w), `diamond`, `tag` (w, h), `barchart`,
`plug` (size), `social` (kind: tiktok|instagram|x). Marks `arrow` (a, b, bend, both, dashed), `head`, `check`,
`cross` (k), `spark` (R), `burst`, `crack` (pts), `qmark`, `play`, `trend` (length, rise), `arc_arrow`.
Primitives `line` / `poly` (pts), `rect` (top-left at, w, h, r), `oval` (rx, ry), `arc` (a0, a1 degrees),
`circle` (r), `curve` (a, via, b, dashed), `dot`, `ngon`; they also take `fill`, `hatch`, `stroke: false`.
Any shape: `color` (ink, accent, soft, warn, or CSS), `lw` (line width x the style's), `at` as a list of
points draws it at each, `jitter` (px). Wrong names are errors with the closest name.

## Check it

`vedit doodle preview flood --style claude-violet` renders a short 1080p draft with the beats spaced
evenly and prints the MP4 path (in a project under `.vedit/doodles/`); `--lang en` sets the row
direction of a short-form spec file. A `.yaml` file with a spec (top level or under `scene:`) works in place
of a scene name.

## Rules

- Fields: `scene` and `beats` (both required). With no `until`/`for` it ends 2.5 s after the last beat.
- Every beat key must be a beat of the scene; a beat left out is drawn at an evenly spaced time.
- Quote beat keys that YAML reads as booleans (`"no"`, `"on"`).
- A beat is the first time its words are spoken from 1 s before `at`, within the cue.
- Everything is drawn 0.75 s before the end; the scene fades out over its last 0.6 s.
- Arabic labels write on right to left in the style's Arabic lettering; Latin left to right.
- The wobble is seeded (library scene: its name; inline: the spec), so a rebuild draws the same strokes.
