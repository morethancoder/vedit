# Words model

One shared way to search words and convert times, used by cuts, cues and subtitles.

Done when:
- [x] Arabic normalisation (alef forms, ى/ي, ة/ه, hamza seats; port `_AR`/`wnorm` from T `build.py`) with unit tests
- [x] `find(phrase, near="A 245.0")` returns the best match's word span; ambiguous or missing matches raise with the closest candidates
- [x] source↔program time mapping from the edl (port T `tools/timeline.py`), tested on holds and removed ranges
