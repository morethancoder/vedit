---
summary: write cuts.yaml: what to remove, pins, chapters
next: vedit cut
---
# cuts.yaml

Status: built. `vedit cut` turns cuts.yaml into the edit list and renders the program; `vedit joins`
prints the joins that read wrong; `vedit listen` checks any excerpt by ear.

## What you write

```yaml
pauses: { max: 0.5, keep: 0.3 }   # defaults; usually omit
fillers: true                     # cut standalone um/uh/aa (not يعني)
cuts:
  - near: A 245.0                 # source clip + approximate time, from the transcript
    say: "يعني شنو"               # the words to remove
    why: filler-repeat            # free text, shown in reports
  - near: A 512.4
    from: "هذا الشي"              # remove from these words...
    to: "خلي أرجع"                # ...through these
  - near: A 668.8
    say: "a long stumble"
    window: 11                    # widen (or narrow) the search around near, in seconds
keep:
  - near: A 408.04
    say: "إم"                     # never cut as a filler ("CMS")
pins:                             # boundaries fixed by ear
  - near: A 300.2
    in: 300.18
    out: 301.06
chapters:
  - near: A 230.0
    title: "chapter title"        # 1.8 s silent hold + chapter card
    kicker: "part 2"              # optional
    logo: telegram                # optional
end: last-word                    # fade to black from the last word
```

## Rules

- Cut by words (`say`, or `from` and `to`), never by raw seconds. `near` only says where to look.
- Words match with Arabic normalisation, so copy them from the transcript as they sound.
- A match must start within 6 s of `near`. A cut further off needs `window:`; two equal matches near
  each other are ambiguous: move `near` closer, quote more words, shrink `window`, or set
  `pick: first|last|<n>` (n counts the matches in the window, in time order).
- A stutter (the same words twice back to back, under 1 s apart) is not ambiguous: the first copy is cut,
  so the last take stays.
- `يعني` is a real word, not an automatic filler: cut it with a `say:` where it hurts.
- `keep:` protects a word the filler rule would cut (an "إم" that is really "CMS").
- ASR times drift up to about 0.5 s. vedit refines every boundary by listening; do not trust word times.
- Pins are for the rare join where listening disagrees. Do not pin by default.
- A pin whose range overlaps no cut becomes a cut by seconds: for a sound the transcript has no word for.
- Never cut a meaning-bearing word as a "filler": one dropped "ما" once flipped a sentence.
- A cut that does not resolve is listed with the closest transcript matches. Fix its words or `near`.

## Running it (`vedit cut`)

- `vedit cut` runs detached (progress in `vedit status`, log in `.vedit/logs/cut.log`); `vedit cut --wait`
  stays in the foreground. `--edl-only` stops after the edit list; `--master` also renders the 4K60 master.
- Steps: resolve every cut -> listen for exact boundaries (`--no-listen` skips it) -> edl -> render.
- A cut that does not resolve fails the run (exit 1) with the list and `next:`: fix those lines, run again.
- Boundary priority per cut: pin, then the listened (refined) boundary, then the quietest 10 ms within
  0.12 s of the word time. Pauses over `pauses.max` shrink to `pauses.keep`. Pieces sit on a 1/30 s grid.
- Output: `.vedit/edl/edl.json` (pieces, holds, total, fade_start) and `.vedit/edl/cuts.json` (the
  resolved cuts and problems). Camera (`cap:`) sources punch in 1.07x on alternate jump cuts: `zoom` on a piece.
- Render: `.vedit/program/proxy.mp4` (1080p30, from the proxy) every run; with `--master` also
  `.vedit/program/master.mp4` (4K60 HEVC, from the camera file; slow, ask for it when the cut is final).
  Each edl piece is its own file in `.vedit/program/pieces/<hash>.mp4` (frame-exact, VideoToolbox); the hash
  covers source, range, hold, fps and encoder settings, so after editing a cut only the touched pieces
  re-encode and the rest join by lossless concat. Reruns with no change reuse every piece. Old piece
  files stay on disk (clean-up comes later). Sound is mixed fresh every run to `.vedit/program/program.wav`:
  48 kHz, 60 ms equal-power crossfade at each join, silent chapter holds, fade out from `fade_start`.
- The report gives pieces rendered vs reused, seconds taken, frames and audio length against the edl, program length, pieces, chapter holds, cuts by kind, pauses shortened, pins applied.

## After writing

- `vedit joins` prints only the joins that read wrong (see below). Fix those lines, then re-run `vedit cut`.
- When cuts change, cues anchored to words still hold; re-check any cue whose words you cut.

## Listening (`vedit listen`)

Ad-hoc checks of what the audio really says; one Studio pass per call, repeats are cached.

- `vedit listen A 300 312`: words of that source excerpt, `t0-t1 word | …`, in source seconds.
- `vedit listen --splice A 668.78:672.2 A 668.78:674.1`: for each `CLIP IN:OUT` candidate cut, hears 1.8 s before
  `IN` joined to 1.8 s after `OUT` and prints one line per candidate. Read it as the viewer would.
- `vedit listen --program 412.5 17.0:21.5`: reads about 2.2 s around program times (or `S:E` ranges) from the
  built program audio; run `vedit cut` first.
- `--json` returns the same results as structured data.

## Checking joins (`vedit joins`)

Needs the built program (`.vedit/program/program.wav`). Transcribes it through Studio, then compares the words
heard around every join with the words the cut should have left (source words minus what the edl removed).

- Detached when the Studio pass is needed (`vedit status`, log in `.vedit/logs/joins.log`); `--wait` stays in the
  foreground. The transcript is cached in `.vedit/program/P.words.json` (program time, with each word's source
  time), so a repeat is quick. `--force` transcribes again.
- Each flagged join prints `program time  clip out>in  expected: before ‖ after`, the `heard:` line and the reason.
  Everything else is one count. `--all` prints every join; `--json` returns them structured.
- Reasons: a clipped word (`يك` for `يكون`), a garbled word or run, words missing at the join, a negation or
  number dropped (the "ما" trap), a removed word still heard, a word heard twice across the join.
- Spelling variants (تيليغرام / تلغرام) and fillers do not count. Each flagged join is listened to a second time
  on its own excerpt and kept only if it shows there too; `--no-confirm` skips that.
- A natural repeat beats a broken word: the fix is to drop the cut or pin it in `cuts.yaml`, then `vedit cut`.
- It cannot hear a cut that left a grammatical hole (a verb removed): read the `expected` line too.
