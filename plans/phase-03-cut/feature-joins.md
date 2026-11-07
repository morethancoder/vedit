# vedit joins

Find the joins that sound wrong without reading all of them.

Done when:
- [x] transcribes the program audio (Studio) and maps its words back to source time
- [x] per join, compares heard words with expected words (source words minus the cut, normalised); prints only mismatches with before ‖ after text
- [ ] on the fixture it flags the known bad joins and few false alarms (record counts in the leaf's commit message) (open: 23 of 159 flagged, ~7 look like ASR false alarms; only 3 of the 21 comparable T-bad joins flagged, most read fine in the fixture's own cut)

## Refs

- port T `tools/joins.py`; the diff is new
