

- Progress: 2026-11-04 — Pre-merge re-verification of tests/test_guard.py.

## 2026-11-04 — Pre-merge re-verification

- `tests/test_guard.py` on branch `247-task-implement-hammer-guard-integri`:
  18 passed (203s) when run as a file.
- Full suite on that branch: 6 failed / 105 passed / 1 skipped — the 6 failures
  are the pre-existing baseline (4 `test_robustness`, 2 `test_worktree_system`,
  tracked by 243/245). Verified by a control run on `main`: the same 6 failures.
- One run transiently showed a 7th failure,
  `test_tasks_modular.py::test_restore_and_undo`. That test is a pre-existing
  order-dependent flake (passes standalone and in every pairwise ordering
  tried; failed once in full-suite order, passed on the repeat full-suite run).
  No fix applied — it belongs to the pre-existing flake tasks, not to this one.

### Known structural note (unchanged from 2026-11-03)
The tests live on the 247 branch rather than on `248-...`, because 248 is the
pair task for 247 and the tests are inseparable from the tool they exercise.
Branch `248-task-write-user-tests-for-247-imple` therefore carries no unique
commits; the deliverable is delivered through the 247 branch merge. This is the
recorded, accepted deviation for this task.

## 2026-11-03 — User tests for the guard tool

The user tests live in `tests/test_guard.py` on branch
`247-task-implement-hammer-guard-integri` (same branch, since 248 is the pair
task for 247 and the tests are inseparable from the tool they exercise).

18 tests across 4 classes:

**TestGuardScan** (read-only reporting)
- duplicate ID reported exactly once, naming both refs
- scan never mutates `.tasks`
- `rebuild` twice → byte-identical anomaly list (determinism)
- adding a branch changes the verdict set in exactly one way

**TestGuardGate** (the enforcement point)
- duplicate ID cannot pass a gate; exit 1 + the folder did NOT move
- state duplicate (same id in two state folders) rejected — the 178/181 scenario
- `--force` overrides, prints the bypass banner, and records the event
- a clean task passes READY and PROGRESSING
- remote duplicate is WARN only — never blocks

**TestGuardCache** (the cache is disposable)
- corrupt cache self-heals and still returns the right verdict
- unwritable cache → fail closed with a message naming `guard rebuild` + `--force`,
  and the pipeline gate rejects with the task in place
- total ref loss after a known non-empty state → GUARD_UNAVAILABLE, not "empty repo"
- verdict identical from the main root and from inside a task worktree
- duplicate worktrees for one task reported
- warm verdict latency < 1s (measured ~20-30 ms)

**TestGuardIntegration**
- `tasks init-hooks` from inside a worktree writes to the COMMON hooks dir (F9)
- `hammer guard scan` reachable through the dispatcher
- `guard hooks --install` writes the wrappers

Fixture notes (why the base class is extended):
- The harness clones the repo then checks out `main`, so files that exist only on
  the task branch are missing; `_install_guard_into_fixture` copies them in.
- The fixture inherits the real `tasks` branch content (ids up to 246), so created
  tasks use `BASE_ID = 9001` to avoid collisions.
- `load_guard_engine()` drops stale `tasks_ai` entries from `sys.modules` because
  other test modules import `tasks_ai` from fixture clones.

### Verification
- `tests/test_guard.py`: 18/18 when run as a file.
- Full `python3 -m pytest tests/`: only the 6 pre-existing failures remain
  (4 in test_robustness, 2 in test_worktree_system — tracked by tasks 243/245,
  unrelated to guard).