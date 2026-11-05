- [x] every guard code is REJECT with no config, dev, or per-code exemption
  - Verified: `test_severity_for_is_always_reject` checks all 9 codes return
    REJECT from `_severity_for()`, and `test_no_warning_tier_exists` asserts
    `SEVERITY_WARN` and `WARN_CODES` no longer exist in the module. The
    `guard.enforce` / `guard.fail_open` attributes are gone from the
    constructor (asserted by `test_no_enforce_or_fail_open_switches`).
- [x] guard.enforce and guard.fail_open config keys removed
  - Both reads deleted from `GuardEngine.__init__`; the `if engine.fail_open`
    branch in `GuardGateHook` and in `guard.py cmd_check` deleted.
    `plan-guard.md` updated to document them as removed. `guard.staleness_warn_min`
    is retained (an operational print, not a verdict exemption).
- [x] test fixtures create real branches in dev mode
  - The dev-mode severity degradation is removed, so fixtures are no longer
    exempt from `GUARD_BRANCH_MISSING`. Two tests that created tasks at real ids
    were colliding with real branches; fixed by adding a shared `seed_counter()`
    to `HammerTestBase` and seeding 9000, following the existing `BASE_ID = 9001`
    convention in `tests/test_guard.py`.
- [x] guard never mutates repo state
  - Verified: `test_guard_never_mutates_the_repo` snapshots `for-each-ref` and
    `worktree list --porcelain` before and after `scan` + `check` and asserts
    both are unchanged. The guard writes only its disposable cache DB and its
    own append-only anomalies log.
- [x] existing guard tests updated to assert blocking behavior
  - `test_remote_duplicate_warns_but_does_not_block` rewritten as
    `test_remote_duplicate_blocks`, asserting the task does not move and stays
    in `backlog`. Plus 5 new `TestGuardStrictness` tests.

## Measured impact (not assumed)

Cross-referencing `guard scan --json` against the 15 live tasks with anomalies
shows **zero newly-blocked live tasks**: every task carrying a WARN-tier code
also carried a hard-REJECT code. The warning tier was dead weight in this repo.

Full suite: 6 failed / 113 passed / 1 skipped — the 6 are the pre-existing
baseline (243/245). `guard check` tests green: 27/27.
