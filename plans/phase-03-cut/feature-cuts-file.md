# cuts.yaml

Load and validate the cut file the model writes.

Done when:
- [x] every form in docs/formats.md parses: `say`, `from`/`to`, `pins`, `fillers`, `pauses`, `chapters`, `end`
- [x] each cut resolves to a source range via the words model; unresolved ones are listed with closest matches, never silently skipped
- [x] T `tools/cuts.py` `PHRASES` + `OVERRIDES` convert into a cuts.yaml for the fixture (one-off script kept in `scripts/convert/`)
