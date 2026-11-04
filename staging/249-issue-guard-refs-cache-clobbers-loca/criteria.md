- [x] refs table stores local and remote entries without collision
  - Verified: `tests/test_guard.py::TestGuardRefs::test_refs_table_holds_local_and_remote_rows`
    asserts `kind='branch'` for the local name and `kind='remote'` for
    `origin/<branch>` in the same table after `rebuild()`. On the live repo,
    `branch`-kind rows went 154 -> 240 after the fix.
- [x] main is kind=branch
  - Verified: `test_current_branch_keeps_local_kind`. Before the fix the cache
    stored `main|remote` despite main being the current local branch; after the
    fix `main` is `branch` with `origin/main` preserved alongside it.
- [x] a promoted task with a pushed branch passes the DONE gate
  - Verified: `test_promoted_task_with_pushed_branch_is_not_rejected` — no
    `GUARD_BRANCH_MISSING` in `verdict(BASE_ID, "STAGING", "DONE", branch)`
    when a remote twin exists. Confirmed these 4 tests FAIL against the
    pre-fix code before re-applying the fix. End-to-end gate on a real task
    (248) is verified immediately after this merge.
- [x] full test suite unchanged from baseline
  - Verified: `python3 -m pytest tests/` on branch 249 = 6 failed / 109 passed /
    1 skipped; main has no `tests/test_guard.py`, so 87 + 22 = 109. The 6
    failures are the pre-existing baseline (243/245).
