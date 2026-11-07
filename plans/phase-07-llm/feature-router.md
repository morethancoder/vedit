# Router

One way to call a cheap model with a saved prompt.

Done when:
- [x] prompts in `prompts/*.md` with a header (preferred model, JSON schema, batch size); ported from T `work/*-prompt.md`
- [x] Claude via `claude -p --model <m> --tools ""`; gemma via Ollama `/api/chat` `format: json`; fallback on error, limit, or invalid output (3 tries per batch)
- [x] every call logged to `.vedit/logs/llm.jsonl` (model, time, fallback reason); `--model` forces one
