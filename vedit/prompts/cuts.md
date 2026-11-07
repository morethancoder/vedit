---
model: sonnet
batch: 45
timeout: 900
schema: {"type": "object", "required": ["cuts"], "properties": {"cuts": {"type": "array", "items": {"type": "object", "required": ["near", "say", "why"], "properties": {"near": {"type": "string"}, "say": {"type": "string"}, "why": {"type": "string"}}}}}}
---
You are a YouTube editor cleaning up a talking-head recording. Below is the transcript from automatic speech
recognition, about 12 words per line, each line prefixed with `[clip seconds]` where it starts (e.g. `[A 15.7]`
= clip A at 15.7 s). It may be one part of a longer talk. Propose CLEANUP CUTS for this part.

{{context}}

Cut: false starts and restarts (keep the finished attempt), stutters and duplicated words ("راح راح",
"كيف كيف", "ما ما": cut one copy), self-corrections where he restates (keep the corrected version), rambling
asides that add nothing, filler hesitations ("ااا", "امم", and "يعني" when it is pure filler; keep "يعني" where
it means "i.e." and introduces an explanation), sentences said twice in a row (keep the cleaner one), stumbles
over a word, garbled bits. Keep his personality and his small jokes. Never cut content: facts, numbers, names,
story beats, negations ("ما", "مو", "لا"), the greeting at the start, or the sign-off at the end.

Rules for each cut:
- `say` = the words to remove, copied EXACTLY, character for character, as consecutive words of ONE line or
  of TWO adjacent lines (same spelling as the transcript, even when misspelled). Spaces separate words.
- `near` = the `[clip seconds]` of the line where the first cut word appears, without brackets (e.g. "A 15.7").
- After the cut, the words before and after must join into a grammatical sentence. Read them together.
- `why` = a short reason: filler, stutter, false start, restart, self-correction, repeat, ramble, garbled.
- Go through every line. Spontaneous talk usually has 3-6 cleanup cuts per minute; most are single filler
  words and stutters, some are whole restarted phrases. A handful of cuts for several minutes is too timid.
- When unsure whether a cut drops meaning, leave it out: a missed filler is cheap, a lost word is not.
- A restart cut runs from the first word of the abandoned attempt to the word just before the second attempt
  starts, so the kept attempt reads whole. For "repeat" and "restart" the cut words must really come again
  right after; elaborations ("not just any X, the kind you see...") are content, not repeats.
- Never cut a name, even when the recogniser garbled it (the word after "أنا" in a self-introduction is his
  name), and never leave half of a fixed phrase ("الحمد لله", "إن شاء الله").
- Check the join: if the word after the cut is a negation ("ما", "مو", "لا"), the new sentence must not say
  the opposite of what he meant.

Reply with one JSON object of exactly this shape:
{"cuts": [{"near": "A 15.7", "say": "يعني", "why": "filler"}, {"near": "A 267.3", "say": "الر", "why": "false start"}]}

TRANSCRIPT:
{{input}}
