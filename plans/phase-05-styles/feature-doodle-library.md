# Doodle library

Hand-drawn explainers from a short spec instead of hundreds of lines per scene.

Done when:
- [x] primitives (seeded wobble strokes, fills, arrows, text) and icons (bot, phone, laptop, server, people, chart, gate, logos) ported from T `doodles.py`
- [x] the 12 Telegram scenes and C's scenes are in the scene library; a scene can also be an inline spec (elements, layout, beats) in cues.yaml
- [x] line style and lettering come from the pack's `doodle.yaml`; `vedit doodle preview <scene>` renders a short check clip

## Approach

Scene spec = elements with positions/relations + which words draw them. Keep the RNG seeded so output is
deterministic. This leaf may need `expand` into primitives / scenes / spec.

## Done (2026-11-05)

- `vedit/doodles/`: geom (polylines, wobble) -> scene (strokes, labels, timings) -> marks, icons -> shapes (spec
  vocabulary) -> spec (validate, short form, draw) -> library (`scenes/*.yaml`, cue `scene:`) + style
  (`doodle.yaml`). Not split into child leaves: one engine, delivered whole.
- 19 library scenes as YAML (T's 12 Arabic, C's 7 English), seeded by name like T: 16 give byte-identical SVG to
  T's own render; alwayson, experience, request differ only in element ids (T opens empty groups before labels).
  Strokes, fills, labels and timings all equal T's (`tests/test_doodles.py` pins `flood`).
- Each pack's `types/doodle.html` draws the scene with T's draw-on motion (pen dashoffset, fills, RTL/LTR
  write-on, spin, float, fade); eases come from `doodle.yaml motion`.
- Fixture check: `~/Demos/vedit-fixture-tele-doodle/.vedit/build/sheet-doodles-vs-T.jpg` (vedit | T, the 12
  cues at end state over the footage) and `sheet-doodles-violet.jpg` (remote, harness, flood in claude-violet).
