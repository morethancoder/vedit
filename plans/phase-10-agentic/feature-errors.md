# Error codes

Agents branch on a code, not on English text.

Done when:
- [x] every failure (VeditError, RunError, usage) carries `code` from one table: `usage`, `not_built`, `stale`,
      `busy`, `missing_tool`, `no_disk`, `bad_input`, `failed`, `timeout`
- [x] exit codes: 0 ok, 1 failed, 2 usage, 3 busy (a job is running), 4 needs an earlier step or input,
      5 environment (tool, disk), 124 timeout
- [x] `vedit guide errors` prints the table with the usual fix per code; codes are explicit where agents branch
      (busy, no_disk, timeout, missing_tool) and inferred from exit + wording at the other ~150 sites (`infer_code`, tested)
