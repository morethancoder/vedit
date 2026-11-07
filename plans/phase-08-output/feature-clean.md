# vedit clean

Get disk back without losing the edit.

Done when:
- [x] `vedit clean` removes frame caches, chunks and scratch media in `.vedit/`, prints freed space per path and total
- [x] `vedit clean --posted` also removes renders, proxies, program, cut-outs and the originals behind `src/` (recorder projects via the importer's `originals()`, exports outside them kept as likely clones); lists everything with sizes and asks first
- [x] keeps cuts.yaml, cues.yaml, custom/, subs/, youtube/, transcripts
