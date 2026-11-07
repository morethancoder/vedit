---
summary: cheap models draft summary.md and a cut list; the model router behind them
next: vedit summarize
---
# Drafts from cheap models

Cheap models draft; you decide. Haiku writes the summary, Sonnet drafts cuts, and nothing they write is final:
`summary.md` saves you reading the raw transcript cold, `cuts.proposed.yaml` is a list to review, never
`cuts.yaml` itself.

## The router: `vedit llm`

```
vedit llm                            # saved prompts and their preferred model
vedit llm summary                    # run one on the project's transcript, print its JSON
vedit llm cuts --model sonnet > cuts.json
vedit llm summary --input talk.txt --notes outline.txt
```

- Prompts ship in vedit (`vedit/prompts/*.md`): a header names the preferred model, the JSON schema the reply
  must match and the batch size (transcript lines per call), then the prompt with `{{context}}` and
  `{{input}}` slots.
- `--model auto` (default) tries the prompt's model, then the next in Haiku -> Sonnet -> gemma4 cloud
  (Ollama). A reply that is not valid JSON for the schema is retried 3 times per batch, then the next model
  runs. A usage or weekly limit moves on at once, so a limit never blocks the edit.
- `--model haiku|sonnet|gemma` forces one model, no fallback.
- `--notes FILE` adds the speaker's outline as context; `--input FILE` runs on any text instead.
- Claude runs as `claude -p` on the creator's subscription with Claude Code's own prompt, tools and MCP servers off,
  so a call costs only its prompt. Reports show tokens and the list price.
- Every call is logged to `.vedit/logs/llm.jsonl`: model, try, tokens, seconds, and why it fell back.

## `vedit summarize`

```
vedit summarize                       # summary.md next to project.yaml, on Haiku
vedit summarize --notes outline.txt   # give it the outline you recorded from
vedit summarize --force               # redo although the transcript has not changed
```

`summary.md` holds chapters (titles in the talk's language, story beats with every number and name kept),
12-25 visual moments worth a graphic, likely ASR errors, and names and terms. Every time is a source time
(`A 231.4`), the same form as `near:` in cuts.yaml and cues.yaml, and vedit checks each one exists before it
writes the file. Read it instead of the raw transcript, then open `.vedit/words/<clip>.txt` only where you need
the exact words. It is a draft: misheard words can still slip into a beat; the ASR-errors list says where.

Cached by the transcript, the prompt and the notes; a second run costs nothing.

## `vedit propose-cuts`

```
vedit propose-cuts                    # cuts.proposed.yaml next to cuts.yaml, on Sonnet
vedit propose-cuts --notes outline.txt --force
```

- Writes `cuts.proposed.yaml` in the cuts.yaml format, each cut with `why`. It never writes `cuts.yaml` and
  `vedit cut` never reads the proposal: you copy the cuts you agree with.
- Every cut is located by its words (inside the transcript line it names) before it is written; cuts that do
  not match or overlap another are left out and listed. Too many misses and the batch is retried.
- Risky cuts come first, marked `# RISKY:` with the reason: they remove a negation ("ما", "مو", "لا"), a
  number, a name (project.yaml `hint`, Latin words) or a long stretch that may be story content. Start there.
- Each cut has a `# ... before [cut] after ...` line: read it as one sentence to check the join.
- `# REPEAT:` marks a stutter whose words occur twice within a second: cutting either copy sounds the
  same, but `near` cannot say which, so word search reports it as ambiguous.
- A draft, not an edit: on the Telegram video Sonnet's list was roughly 80% right; some "filler" cuts removed
  real words. Fillers like "ااا" are cut anyway by `fillers: true` in cuts.yaml.
