---
summary: check the build before rendering: snapshots, flags, draft
next: vedit review
---
# Review

## Loop

1. `vedit review` snapshots every graphic at its peak (all of it drawn, before it leaves) into contact
   sheets, and prints only the flagged cues, each with its sheet and cell number.
2. Open the sheets (flagged cells first: red frame) and look at them. vedit measures; you judge the look.
3. Fix `cues.yaml` or the style, `vedit build`, `vedit review` again.
4. `vedit draft` renders `.vedit/hf/` at 1080p to `.vedit/renders/draft.mp4`, checks length and audio, and opens
   it in QuickTime. Watch it there. An unchanged build reuses the file; `--force` renders again, `--no-open`
   skips QuickTime.
5. Only then `vedit render` (see `vedit guide render`).

## vedit review

- Output in `.vedit/review/`: `sheet-01.jpg`, … (12 cells each, labelled `<cell>. <cue id>  mm:ss`),
  `report.json` (every cue: peak, sheet, cell, flags, measured texts). `--json` prints the same.
- Flags, measured in the browser at the peak:
  - `face`: text within 40 px of his face (graphics over the footage only; full-frame scenes and big
    words behind the cut-out are exempt).
  - `small`: text rendered under 22 px at 1080p.
  - `contrast`: text against the frame behind it under 3:1 (WCAG, large text).
  - `drawing`: an element still drawing when the graphic starts to fade out.
- On the sheet: red boxes = the flagged texts, orange = the face box with its margin.
- Snapshots are cached by the content of `.vedit/hf/`: a rerun without a new build takes seconds.
  `vedit review --force` snapshots again.
- No flags does not mean it looks right: still look at every sheet.

## Rules

- Never open HyperFrames Studio to review: use the sheet and the draft MP4.
- Do not edit files under `.vedit/hf/`: the next build overwrites them.
- Fix flags at the source (cues, cuts, style), not in generated files.
