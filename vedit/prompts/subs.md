---
model: sonnet
batch: 40
timeout: 600
schema: {"type": "object", "required": ["src", "tr"], "properties": {"src": {"type": "object"}, "tr": {"type": "object"}}}
---
These are subtitle cues of a YouTube video. The speaker talks {{src_lang}}.

{{context}}

The {{src_lang}} text is raw speech recognition and has errors. For EVERY cue id produce:
- "src": the cleaned {{src_lang}} line: fix recognition mistakes and misspellings, keep the speaker's own dialect and
  wording (do not convert to the standard written language, do not summarise), remove leftover stutters. Write
  product and tech names, commands and file names in Latin letters exactly as they are written (for example
  PowerTeleBot, MCP, Claude, ChatGPT, Python, JavaScript, Telegram Stars, `.env`, `--flag`); use the names listed
  above to correct near-homophones.
- "tr": a natural {{tr_lang}} subtitle translation of that cue: same meaning, conversational, concise. Keep product
  names and commands in Latin.
Cues often split mid-sentence; keep each line's content within its own cue (do not move words across cues).

Output ONLY JSON: {"src": {"1": "...", "2": "..."}, "tr": {"1": "...", "2": "..."}} with exactly the same ids as the
input.

CUES (id: text):
{{input}}
