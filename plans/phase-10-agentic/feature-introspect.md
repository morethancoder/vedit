# vedit commands --json

An agent reads the whole command surface as data instead of scraping `--help`.

Done when:
- [x] `vedit commands --json` lists every command: name, summary, guide topic, example, flags (name, type, default,
      choices, help, required), and `effects` (`reads`, `writes`, `renders`, `long`, `destructive`)
- [x] every JSON value vedit prints carries `"v": 1` (envelope version) and, where files were written,
      `artifacts: [{"path", "kind"}]`
- [x] a test fails when a command is added without `effects`
