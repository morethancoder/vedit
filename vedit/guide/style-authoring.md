---
summary: build a new style pack from screenshots or a video: new, try, fork, compare, pick, save
next: vedit style new
---
# Authoring a style

You build the look; vedit renders and measures it. vedit never judges style and calls no model for it: you
look at the images (you can see them), the creator picks between options.

## The loop

1. `vedit style new <name> --from <dir|image|video> [--lang ar|en]` makes a draft at
   `~/.config/vedit/styles/drafts/<name>/`:
   - `refs/`: the screenshots copied (up to 16), or a video's frames sampled at scene changes (up to 8;
     evenly spaced when it has few cuts).
   - `pack.yaml`: base's tokens with `extends: base`, the palette from OpenCV k-means (10 clusters, those
     under 0.2% of the pixels dropped): `accent` = the most saturated cluster with Lab chroma >= 20, however
     small (a grey background never wins; none vivid keeps base's), `ivory` / `ink` = lightest / darkest when
     light / dark enough for text, every cluster as `ref1..refN`. Themes that used base's colours follow.
   - `types/*.html`, `partials/*.html`: copies of base's, yours to edit. Sounds, logos stay inherited.
   - `fonts/` (empty, for your font files) and `doodle.yaml` (base's doodle look, to edit).
   - `brief.md` to fill (each line has a placeholder to replace), `palette.json`, `history.md`.
2. Look at `refs/`. Fill `brief.md`: type, shapes, motion, per cue type, questions for the creator.
3. Edit the pack (format: `vedit guide styles`):
   - tokens in `pack.yaml`: `colors`, `themes` (text, sub, kicker, shadow), `motion` (eases, timings).
   - fonts: not identified for you. Name the families you see, propose free ones (`fc-list`), copy the
     files into the draft's `fonts/` (`.woff2` or `.ttf`) and declare each in `pack.yaml`, a list that
     replaces base's: `fonts: [{family: "DM Sans", file: fonts/dm-sans-500.woff2, weight: 500}]`, plus
     `style: italic` for italics. Use the family in the `font:` stacks, which templates read as
     `{{&font.<key>}}`: `text`, `mono`, `hand`, `ui` (kicker, sub, chip label, step text; follows `text`
     unless set) and any key you add (`serif`, `sans`). Bundle only OFL/free fonts. An Arabic-capable
     pack puts its Arabic face in every stack.
   - doodle look: the draft's `doodle.yaml` keys `stroke`, `accent`, `soft`, `warn` (colours), `width`,
     `wobble` (line), `lettering` (`latin`, `arabic`, `mono` stacks, `arabic_scale`), `shadow`, `motion`.
   - shapes and motion in `types/<type>.html` (slot headers stay as they are: cues depend on them).
4. `vedit style try <name>` renders the specimen and prints its path and the palette distance:
   - `specimen/specimen.png`: every cue type (label, label on light, chip, kinetic, big-number, chapter,
     doodle, screen, plug) with the same sample cues for every pack (`vedit/styles/specimen.yaml`), Arabic
     or English by the pack's first `lang`, the refs in a column beside them, pack colours and ref
     clusters on top. A tile that cannot render says why (its cue fields or template).
   - `--clip` adds `specimen/specimen.mp4`: a ~12 s 1080p draft of kinetic, label, chip, big-number in
     motion. Open it in QuickTime (`open -a "QuickTime Player" <file>`), never a Studio preview.
   - palette distance: for each pack colour (not `ref*`), CIE76 ΔE to the nearest ref cluster, small
     saturated ones included; the mean is printed. Under 3 is the same colour, ~10 a near shade, over 25 another colour. It measures; it does
     not say the look is right.
   - only what changed renders again (content hash); `--force` renders anyway. A pack with problems is
     not rendered: the error lists every one.
   Look at the sheet next to the refs, edit, try again.
5. `vedit style fork <name> <variant>` copies the draft to `drafts/<name>@<variant>/` (pack name
   `<name>@<variant>`), so two directions can be shown. Edit it, then `vedit style try <name>@<variant>`.
6. `vedit style compare <a> <b> ...` (or `vedit style compare <name>` for a draft and all its options)
   writes one sheet, one column per pack, one row per cue type, at
   `~/.config/vedit/cache/specimens/compare/<a>+<b>.png`, renders what is missing and opens the clips in
   QuickTime for the creator. `--no-open` skips the clips (agents, tests).
7. The creator picks; you never pick for him. `vedit style pick <name> <variant> --why "<his reason>"` keeps that
   option as `<name>` (variant `main` = the draft itself), moves the others to `drafts/.archive/`, and
   logs the date, the pick, what it was picked over and the reason in `history.md`.
8. `vedit style save <name> --global --keywords "warm doodle arabic"` (or `--channel <handle>`) checks the
   pack, refuses on any problem or while forks remain, and moves it to `~/.config/vedit/styles/<name>/`
   (or `~/.config/vedit/channels/<handle>/styles/<name>/`) with `refs/`, `brief.md`, `history.md`. A pack
   already there is archived, and only with `--yes`.
9. Use it: `style: <name>` in project.yaml or cues.yaml, then `vedit build`.

Built-in and saved packs can be tried and compared too (`vedit style try yellow-doodle`); a built-in's
specimen goes to `~/.config/vedit/cache/specimens/<name>/`, never into vedit itself. Names resolve drafts,
then the channel (`--channel`), global, built-in.

## Rules

- vedit renders and measures; you and the creator judge the look.
- Every pack is shown with the same sample cues, so packs compare fairly. Do not edit `specimen.yaml` to
  flatter a pack.
- Keep `refs/`, `brief.md`, `history.md` with the pack.
- `--json` on every action gives one JSON value with the paths, tiles, problems and palette numbers.
