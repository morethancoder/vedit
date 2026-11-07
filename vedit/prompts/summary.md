---
model: haiku
batch: 0
timeout: 600
schema: {"type": "object", "required": ["chapters", "visual_moments", "asr_errors", "terms"], "properties": {"chapters": {"type": "array", "items": {"type": "object", "required": ["start", "title", "about", "beats"], "properties": {"start": {"type": "string"}, "title": {"type": "string"}, "about": {"type": "string"}, "beats": {"type": "array", "items": {"type": "object", "required": ["at", "text"], "properties": {"at": {"type": "string"}, "text": {"type": "string"}}}}}}}, "visual_moments": {"type": "array", "items": {"type": "object", "required": ["at", "kind", "show"], "properties": {"at": {"type": "string"}, "kind": {"type": "string", "enum": ["number", "diagram", "list", "quote", "logo", "joke", "screen", "other"]}, "show": {"type": "string"}, "words": {"type": "string"}}}}, "asr_errors": {"type": "array", "items": {"type": "object", "required": ["at", "heard", "likely"], "properties": {"at": {"type": "string"}, "heard": {"type": "string"}, "likely": {"type": "string"}}}}, "terms": {"type": "array", "items": {"type": "object", "required": ["term", "note"], "properties": {"term": {"type": "string"}, "note": {"type": "string"}}}}}}
---
You are helping edit a talking-head video. Below is the full word-timed transcript (automatic speech
recognition, so expect misheard words). Each line starts with `[clip seconds]`, e.g. `[A 12.6]` = clip A at
12.6 s.

{{context}}

Write a compact editor's brief so the editor does not have to read the raw transcript. Reply in ENGLISH, except
where told to quote the spoken words.

1. chapters: 6-15 sections covering the whole talk in order. `start` = the `[clip seconds]` of the line where
   the section begins, copied exactly (e.g. "A 51.6"); a section ends where the next one starts.
   `title` = 3-6 words in the language the speaker uses (it becomes a chapter card). `about` = one English sentence.
   `beats` = 2-5 story beats per section, each with the `at` of the line where it starts. Keep every number,
   name, product, date, price, quote and anecdote exactly.
2. visual_moments: 12-25 moments where an on-screen graphic would help: a number or stat to show big, a
   process to explain with a hand-drawn diagram (list its elements in the order he mentions them), a list, a
   quote, a product name or logo, a joke or punchline, a screen worth showing. `at` = the line's
   `[clip seconds]`; `kind` = number|diagram|list|quote|logo|joke|screen|other; `show` = what to put on
   screen, in English; `words` = the spoken words the graphic belongs to, copied from the transcript.
3. asr_errors: words the recogniser probably got wrong, judged from context (product names, English terms
   heard as Arabic, near-homophones). `heard` = as written in the transcript; `likely` = what was said.
   Be suspicious where a sentence contradicts the story around it (a dropped or misheard negation such as
   "مو شغال" heard as "مشغل"), or a number does not fit (a group name, a year, a count): list it here and do
   not state the doubtful reading as fact in the chapters.
4. terms: names, products, brands and technical terms, one line on what each is. Use the spelling the
   speaker means, not the misheard one.

Reply with one JSON object of exactly this shape (these key names, every key present):
{"chapters": [{"start": "A 51.6", "title": "...", "about": "...", "beats": [{"at": "A 56.1", "text": "..."}]}],
 "visual_moments": [{"at": "A 12.6", "kind": "number", "show": "...", "words": "..."}],
 "asr_errors": [{"at": "A 786.7", "heard": "...", "likely": "..."}],
 "terms": [{"term": "...", "note": "..."}]}

TRANSCRIPT:
{{input}}
