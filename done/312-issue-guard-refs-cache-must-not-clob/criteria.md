- [x] refs table stores local and remote entries without collision
  - Verified: `tests/test_guard.py::TestGuardRefs::test_refs_table_holds_local_and_remote_rows`
    asserts `kind='branch'` for the local name and `kind='remote'` for
    `origin/<branch>` in the same table after `rebuild()`. Live-repo effect:
    `branch`-kind rows went 154 -> 240.
- [x] main is kind=branch
  - Verified: `test_current_branch_keeps_local_kind`. Before the fix the cache
    stored `main|remote` despite main being the current local branch; after the
    fix `main` is `branch` with `origin/main` preserved alongside it.
- [x] a promoted task with a pushed branch passes the DONE gate
  - Verified: `test_promoted_task_with_pushed_branch_is_not_rejected` — no
    `GUARD_BRANCH_MISSING` in `verdict(BASE_ID, "STAGING", "DONE", branch)`
    when a remote twin exists. These 4 tests were first confirmed to FAIL
    against the pre-fix code, so they are genuine regression tests.
- [x] full test suite unchanged from baseline
  - Verified: `tests/test_guard.py` = 22 passed in this worktree after the copy
    (18 pre-existing + 4 new). Equivalent full-suite run on the source branch
    was 6 failed / 109 passed / 1 skipped = main's 87 baseline + 22, with the
    6 failures pre-existing (243/245).
