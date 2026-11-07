# File formats

These are the only files the model writes during an edit. Proposals; phase 01 fixes them.

## project.yaml

```yaml
slug: tele-a7-growth-story
lang: ar            # ar | en
dialect: iq         # Studio --dialect (iq, gulf, lev, eg, ma, msa); omit for en
channel: ali-talks    # optional; ~/.config/vedit/channels/<handle>/ (default from config.yaml)
style: yellow-doodle  # optional when the channel has a default
accent: "#FFD60A"   # optional override of the pack's accent
hint: "PowerTeleBot, MCP, Telegram"   # names Studio transcription should favour
sources:
  A: { cap: "~/Library/Application Support/so.cap.desktop/recordings/<project>.cap", camera: raw }
  B: { file: src/screen-1.mov }        # screen recordings, demos
logos: [telegram, octopus, spark]
plug: powertelebot                     # product plug preset (phone demo + URL click)
```

Required: `slug`, `lang`, `sources`. Every source has exactly one of `file` or `cap` (plus optional `camera`);
relative paths start at the project folder, `~` expands, and a missing path is an error. Unknown keys are errors
(with a closest-key suggestion). Durations are never stored: they come from ffprobe.

## cuts.yaml

```yaml
pauses: { max: 0.5, keep: 0.3 }        # defaults; usually omitted
fillers: true                          # cut standalone um/uh/aa (ااا, ام, اه, um, uh, erm, ah)
cuts:
  - near: A 245.0                      # source clip + approx time (from the transcript)
    say: "يعني شنو"                    # the words to remove (matched with Arabic normalisation)
    why: filler-repeat                 # free text; shows up in reports
  - near: A 512.4
    from: "هذا الشي"                   # remove from these words...
    to: "خلي أرجع"                     # ...through these (looked for after `from`)
  - near: A 668.8
    say: "…"
    window: 11                         # seconds either side of near a match may start (default 6)
    pick: last                         # optional: first | last | <n> among the matches in the window
keep:                                  # words never cut as a filler
  - near: A 408.04
    say: "إم"                          # "سي إم إس" (CMS), not an "um"
pins:                                  # boundaries fixed by ear when listening disagrees
  - near: A 300.2
    in: 300.18
    out: 301.06
chapters:
  - near: A 230.0
    title: "علي، البوت مو شغال"        # 1.8 s silent hold + chapter card
    kicker: "الجزء ٢"                  # optional: small line over the title
    logo: telegram                     # optional: a mark from project.yaml `logos`
end: last-word                         # fade to black from the last word over running footage
```

- `يعني` and other real words are never automatic fillers: cut them with explicit `say:` cuts.
- `window:` replaces the default search window of one cut. Two matches whose distances from `near` differ
  by under 1 s still count as ambiguous; narrow `window`, quote more words, or set `pick:`.
- Stutters are not ambiguous: identical copies back to back (no word between, under 1 s apart) resolve to
  the FIRST copy, so a restart keeps the last take. `pick: first|last|<n>` (1-based, in time order among all
  matches in the window) overrides that; on a `from`/`to` cut it applies to `from`.
- A cut ends where the next word starts (the clip's end if there is none). Cuts are in source time.
- A pin takes over the boundaries of the word cut whose range overlaps `in`..`out` (the one nearest `near`
  if several); listening never moves a pinned cut. A pin that overlaps no cut is a cut of its own, by
  seconds: use it for sounds the transcript has no word for.
- Every cut that does not resolve is reported with the closest transcript matches; none is skipped silently.

## cues.yaml

Every cue is anchored to **spoken words**, so it survives any cut change. `at` finds the phrase near `near`;
`until` (words) or `for` (seconds) sets the end; the engine snaps the window inside one continuous shot.

```yaml
style: yellow-doodle                   # default for every cue; a cue may override with style:
cues:
  - type: label
    at: "فتحت قناتي"
    near: A 92
    logo: octopus
    kicker: "قبل ٤ سنين"
    title: "فتحت قناتي على يوتيوب"
  - type: big-number                   # word behind the head, person cut-out over it
    at: "من 200 ألف"
    near: A 12
    pre: "من 200 ألف إلى"
    word: "1.7M"
  - type: kinetic                      # word-synced spoken text
    at: "البوت مو شغال"
    words: "«شنو البوت مو شغال؟!»"
    highlight: ["مو شغال؟!»"]
  - type: doodle
    at: "البوت عليه ضغط"
    scene: flood                       # a library scene, or an inline spec:
    beats:                             # element -> the words that draw it
      bot: "البوت عليه ضغط"
      flood: "آلاف"
      crash: "ذاك الضغط"
  - type: plug                         # product plug preset from project.yaml
    at: "باور تيلي بوت"
  - type: custom                       # escape hatch: any HTML/GSAP sub-composition
    at: "…"
    file: custom/intro.html
    for: 4.0
    box: [100, 100, 500, 300]          # optional: where it draws, [x, y, w, h] px in 1920x1080 (default full frame)
    face: ignore                       # optional: skip the face check
```

Slots per type (declared in the pack's `types/<type>.html`; an unknown field, wrong kind or missing required
slot is an error, all reported at once). Required first: `label` logo, kicker, title (sub, mono); `chip` label,
code (logo); `kinetic` words (highlight, center); `big-number` word (pre, color); `doodle` scene, beats; `screen`
source (from, kicker, title, steps); `plug` url, trial (spoken words of those moments); `custom` file (box, face);
`chapter` title (kicker, logo). A custom cue is checked against the face track over its `box` (full frame when
absent, so it warns) unless `face: ignore`. The pack's tokens reach it as CSS variables on its root, with the
pack's @font-face rules: `--vedit-<colour>` (every `colors` key; accent follows the channel), `--vedit-text|sub|kicker|shadow`
(and any other key of the dark theme), `--vedit-font-<key>` (every `font` key: text, mono, hand...). `_` becomes `-`.
A style switch changes them. Beat keys that YAML reads as booleans (`no`, `on`) must be quoted.

Anchoring: `at` + `near` resolve with the words model (`pick`, `window` honoured); without `near`, `at` must
match exactly once in the project. Start = the anchor's first word through the edl. End: `until: "words"` (first
match after the anchor within 90 s; `until_near` pins it), `until: end` (program end) or `for: <seconds>`;
otherwise the type's default: label 6 s, chip 8, big-number 5, screen 8, plug 18; kinetic = last shown word's
onset + 1.2 s; doodle = last beat + 2.5 s; custom has none (`for` required). Beats and `kind: words` slots are the
first match from 1 s before the anchor to the cue's end + 5 s; a miss is a problem on the cue. A cue whose anchor
words were cut away is kept with a problem. Chapters come from cuts.yaml `chapters:` paired in order with the
edl's holds; the card runs from 0.5 s before the hold to 0.9 s after it. Logos: the pack's plus
`custom/logos/<name>.svg|png` in the project. Plug preset: `custom/plug/plug.yaml`, else the channel's `channels/<handle>/plug/plug.yaml` (whole folder
replaced, not merged; `name`, `kicker`, `url`, `trial`
texts; `logo`, `demo`, `hold` files beside it); without it the plug shows brand text only (project.yaml `plug`).
Engine values reach templates as context (see `vedit/graphics/pages.py`): `dur`, `side`, `th.*` theme tokens,
`blur`, per-type numbers (kinetic `words[].at` + `width`, `big.*`, doodle `beats[]`, plug `url_at`...).

Types in v1: `label`, `chip`, `kinetic`, `big-number`, `doodle`, `screen` (screen recording over the blurred
A-roll), `chapter` (generated from cuts.yaml), `plug`, `custom`. Placement (side, theme, blur) is never
written here: the engine decides it from the face track and frame brightness.

## Style pack (`styles/<name>/`)

```
pack.yaml          tokens: colours, fonts (with files), themes (text shadows), motion, sfx map, advances
fonts/             font files the pack needs (ttf/woff2), named in pack.yaml `fonts:`
logos/             svg marks the pack offers (fills as var(--token, fallback) resolve from the theme)
sfx/               mp3 sounds named in `sfx:`
types/<type>.html  one template per cue type: slot header, <style>, body, <script> with the pack's GSAP motion
partials/*.html    shared CSS/JS fragments the templates pull in as {{&part.<name>}} (base css, blur, logo motion)
doodle.yaml        doodle line style and lettering (below); merged down the extends chain
```

`pack.yaml` keys (anything else is an error, with the closest key as a hint):

```
name, extends        folder name; the pack a missing type or token comes from (default: base)
summary, keywords    one line for `vedit styles`; words for `vedit styles find`
lang                 languages the pack is drawn for
colors               name -> colour; templates read c.<name>; `accent` is replaced by a channel accent
fonts                [{family, file, weight, style}]; every file must exist in the pack (or what it extends)
font                 text | mono | hand (+ any the pack's templates read, e.g. serif) -> CSS font-family
                     stacks; an Arabic-capable pack puts its Arabic face inside each stack
themes               dark | light -> {text, sub, kicker, shadow, ...}; placement picks one per cue (th.*)
busy_shadow          denser text-shadow for the dark theme over busy screens
motion               ease_in, ease_out, ease_draw, ease_pop (GSAP eases); in, out, out_lead, scene_out,
                     scene_lead, stagger (seconds); rise (px). Templates read m.<token>
advances, big        big-word metrics: JSON file char -> advance (em), and {track, min_px, max_px, tuck}
logo_motion          {spin: [logo names that keep turning]}
focus                A-roll under full-frame scenes: {blur, brightness, in, out}
sfx, sfx_files       cue kind -> [sound, gain]; sound -> seconds (every sound used needs a length)
```

Packs merge down the `extends` chain (this pack's keys win, mappings merge key by key). A cue type missing
from a pack falls back to its `extends` pack, then `base`. A new look = a new pack folder; the cue files don't
change. v1 ships `yellow-doodle` (from the Telegram video) and `claude-violet` (from the Claude Code in
Telegram video).

Templates use a mustache subset (`{{x}}`, `{{&x}}` raw, `{{#x}}`/`{{^x}}` sections, dotted names, `{{.}}`). The
header `<!-- vedit slots: {name: {kind, required, help}} -->` declares the cue fields the type accepts; kinds:
text, bool, number, list, words, beats, logo, file, box, scene (a doodle library name or an inline spec). The
context names every template gets are listed in
`vedit/graphics/pages.py` (`id`, `dur`, `side`, `dir`, `theme`, `th.*`, `c.*`, `font.*`, `m.*`, `logo.*`,
`part.*`, `blur`, the cue's slots, and per-type values).

The pack checker (`vedit styles`, and `vedit build` before it uses a pack) reports every problem at once:
unknown keys, missing font/sfx/advances files, sounds without a length, unknown `logo_motion` logos, missing
theme tokens or motion tokens, templates whose header or sections don't parse, unknown slot kinds, and
doodle.yaml problems (unknown keys, wrong kinds, a lettering font the pack's own `fonts` lack).

`doodle.yaml` keys (vedit/doodles/style.py; anything else is an error):

```
stroke               main line colour (a CSS colour, or a pack colour name)
accent, soft, warn   fills/highlights, secondary marks and labels, errors; `accent: accent` follows the channel
width, wobble        line weight in px at 1080p (T 4.6); wobble amplitude multiplier (1.0 = T)
lettering            {latin, arabic, mono}: CSS font stacks (families in pack.yaml `fonts`); arabic_scale
shadow               text-shadow behind lettered labels
motion               GSAP eases: pen (strokes, write-on), fill, label (fade-ins), out (scene fade)
```

`pack.yaml` also carries `summary:` (one line) and `keywords:` (for `vedit styles find`). Authored packs keep
`refs/` (the screenshots they were built from), `brief.md` (what the agent saw) and `history.md` (options the creator
picked and why).

Authoring (`vedit style`, `vedit guide style-authoring`): a draft lives at `styles/drafts/<name>/` (extends base;
copies of base's `types/` and `partials/`; `palette.json` holds the refs' k-means clusters, also written to
`colors` as `ref1..`), an option at `styles/drafts/<name>@<variant>/` (pack name `<name>@<variant>`), options
not picked and packs a save replaced at `styles/drafts/.archive/`. A pack's specimen (`specimen.png`,
`specimen.mp4`, `tiles/<id>.png`, `key.json`) is in `<pack>/specimen/`, a built-in's in
`<config>/cache/specimens/<name>/`; render work dirs and compare sheets are under `<config>/cache/specimens/`.
The sample cues are `vedit/styles/specimen.yaml`.

## Doodle scene spec (`vedit/doodles/scenes/<name>.yaml`, or a cue's inline `scene:`)

Full form (the library): `beats:` maps each beat, in drawing order, to steps. A pen pass draws its shapes in one
stroke of `pen` seconds; a text is hand-lettered (Arabic writes on right to left). Times are seconds after the
beat's spoken words; positions px on 1920x1080; the RNG is seeded by the scene name (inline: the spec), so the
same spec gives byte-identical SVG.

```yaml
lang: ar                     # library metadata: lang, about; optional seed
beats:
  bot:
    - pen: 1.0               # pass: pen (s | next), shapes, after, float (px), name, into (named pass),
      float: 4               #       spin {about, rate, after, of}
      shapes:
        - bot: {at: [500, 570], w: 240, h: 210}
        - arrow: {a: [1200, 440], b: [760, 440], size: 18, lw: 0.8}
    - {text: "البوت", at: [500, 790], after: 0.6, size: 64}   # text: at, after, size, weight, color, mono, anchor
```

A shape is `{kind: {params}}`: the kind's own parameters (vedit/doodles/shapes.py, icons.py, marks.py), `at`
for its first two (centre; top-left for rect, window, bubble, barchart; a list of points repeats it), `lw`
(line width x the style's), `color` (ink, accent, soft, warn or CSS), `jitter` (px). Primitives also take
`fill`, `hatch`, `stroke: false`.

Short form (inline in cues.yaml): `elements:` [{beat, one shape, id, at, label, size, color, pen, after, float}
| {beat, text, at} | {beat, arrow: {from: <id or [x, y]>, to: ...}, label}], `layout: row|column` spreads the
elements with no `at` (a row runs right to left for an RTL project). It expands to the full form. The cue's
`beats:` keys must be beats of the scene; one left out is drawn at an evenly spaced time. Errors name the step
and the closest valid name. `vedit doodle list` names the library; `vedit doodle preview <scene>` renders a check.

## Where styles live, and which one wins

```
vedit/styles/<name>/                               built-in
~/.config/vedit/config.yaml                        default channel, default style
~/.config/vedit/styles/<name>/                     global (drafts/ holds packs being authored);
                                                   $VEDIT_CONFIG_DIR replaces ~/.config/vedit
~/.config/vedit/channels/<handle>/channel.yaml     default style, lang, accent, logos
~/.config/vedit/channels/<handle>/styles/<name>/   channel-only packs
~/.config/vedit/channels/<handle>/plug/plug.yaml   channel plug preset (project custom/plug/ overrides it)
```

A name resolves channel → global → built-in. The style used is the first set of: cue `style:`, cues.yaml
`style:`, project.yaml `style:`, channel default, global default, then `base`. `vedit status` prints the winner.
The channel is the project's `channel:`; `vedit channel add|show` manages channel.yaml (style, lang, dialect, accent,
hint, logos as a list of names).
