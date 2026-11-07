# Models: who does what

Measured on the Telegram video (2026-11-04/05). Cheap models draft; Opus decides.

| Job | Model | Result | vedit command |
|---|---|---|---|
| Transcription, listening checks | Studio qwen3-asr (local) | free, verbatim; Whisper formalised Iraqi Arabic | `transcribe`, `cut`, `joins` |
| Transcript summary: chapters, visual moments, likely ASR errors | Haiku | excellent, 52 s | `summarize` |
| First cut list | Sonnet | ~80% right; some "filler" cuts deleted real words | `propose-cuts` (draft only) |
| Join check | code (expected vs heard words) | Sonnet found every problem but half its flags were false | `joins` |
| Doodle scenes | Sonnet | very good, one layout fix: the biggest saving | drafting `cues.yaml` doodle specs |
| Subtitle cleanup + English | gemma4:31b-cloud via Ollama | 25 s, good | `subs` |

**Opus keeps:** what to cut, fixing boundaries the listener gets wrong, which ideas get a doodle and how to
show them, every on-screen line, the snapshot review.

## Router (`vedit llm`)

- One function (`vedit/llm.py: ask`) / command: `vedit llm <prompt-name> [--input file] [--notes file] [--model auto|haiku|sonnet|gemma]`.
- Order for `auto`: the prompt's preferred model, then the next on failure or rate/weekly limit:
  Haiku → Sonnet → `gemma4:31b-cloud` (Ollama, `http://localhost:11434/api/chat`, `format: json`) → stop with a clear error.
- Claude models are called with `claude -p --model <m> --tools ""` (the creator's subscription), with Claude Code's own
  system prompt, MCP servers, settings and slash commands switched off (`--system-prompt`, `--strict-mcp-config`,
  `--setting-sources ""`, `--disable-slash-commands`): ~0.9K tokens of overhead per call instead of ~48K.
  Ids: `claude-haiku-5-5`, `claude-sonnet-5-5` (list price $0.10/$0.50 and $2/$10 per M tokens).
- Prompts live in `vedit/prompts/*.md` with a header: preferred model, expected JSON schema, batch size.
  Outputs are validated (JSON parses, matches the schema, plus a per-command check such as times or words that
  must exist); a failed batch retries up to 3 times, telling the model what was wrong, then falls back.
- Every call logs model, tokens/time and fallback reason to `.vedit/logs/llm.jsonl`.

Prompts to port: summary, cut list (from the Telegram session), subtitle clean+translate
(`tele-a7/work/sonnet-subs-prompt.md`), doodle scene drafting.

## Acceptance run: the Telegram talk rebuilt with vedit (2026-11-06/07, M1 Pro 16 GB)

Copy `~/Demos/vedit-accept-tele`, converted `cuts.yaml` / `cues.yaml`, style `yellow-doodle`.

| stage | wall | model calls |
|---|---|---|
| new (ingest, proxies) | 210 s | none |
| cut (listen + 161 pieces) | 292 s | Studio ASR (local) |
| build (first, 48 graphics + checks) | 396 s | none |
| review | 46 s | none |
| subs (161 cues, ar + en) | 80 s | Sonnet: 12 768 in / 12 328 out tokens, $0.174 list |
| draft 1080p | 411 s (was 1528 s before chunked drafts) | none |
| render 4K60 | 74 min: 4K program 960 s, cut-outs 538 s, 6 chunks 2902 s, join 57 s | none |

Result: 13:08.70 (T 13:08.10), 48 graphics, master 3840x2160 60 fps 47 322 frames (= wanted), 4.99 GB.
Style switch: `style: claude-violet` (one line in project.yaml) on a copy: build 31 s, review 47 s, 48 graphics,
lint + check pass, 1 review flag. The only paid model in the whole run is the subtitle router call.
