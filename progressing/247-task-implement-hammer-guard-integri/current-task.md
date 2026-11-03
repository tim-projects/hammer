---
Task: 247-task-implement-hammer-guard-integri
---

- Progress: 

## 2026-11-03 — Guard implementation (Phase 1 + Phase 2 gate)

### Phase 0 verification (empirical, from this repo)
- R1 `for-each-ref refs/heads` from inside `.task-worktrees/241-...` returns the same 238 refs as the main root → refs are common-dir-wide. Confirmed.
- R2 `git worktree list --porcelain` from a worktree lists all worktrees. Confirmed.
- R3 `git rev-parse --git-path hooks` from a worktree resolves to `<mainroot>/.git/hooks` → hooks are shared. Confirmed; this is the F9 fix basis.
- R6 Local `tasks` branch AND `origin/tasks` both exist → prefer `origin/tasks`, fall back to local.
- R9 Refname charset: branch convention regex `^[0-9]+-(task|issue|docs)-[a-zA-Z0-9-]+$` holds for all task refs; non-conformant names (e.g. `178-finalization`) are reported, not fatal to the parser.

### Findings on the live repo (guard scan, read-only)
- 24 duplicate local IDs (1, 2, 3, 6, 115, 178, 193, 213, 220, 222-225, 232-237, 239-245, 306, 307).
- 2 GUARD_STATE_DUPLICATE: 137 in done+rejected; 232 in staging+done.
- 143 GUARD_REMOTE_DIVERGENCE (local folders whose branch is gone).
- 24 GUARD_BRANCH_NONCONFORMANT (e.g. `178-add-type-to-modify`).

### Delivered
1. `tasks_ai/guard_engine.py` — SQLite cache (WAL, `busy_timeout=5000`) at
   `<common_git_dir>/hammer-guard/guard.db`, refresh from two subprocesses
   (`for-each-ref` + `ls-tree <tasks-ref> */meta.json`) + a `.tasks` directory
   walk + `git worktree list --porcelain`. Disposable: `rebuild` wipes and
   re-derives; a corrupt cache self-heals on the next verdict (rebuild-before-reject).
   Ref loss after a known non-empty state raises `GUARD_UNAVAILABLE` (fail closed).
2. `guard.py` CLI — `check`, `scan [--all --json --fix-plan]`, `refresh [--fetch]`,
   `rebuild`, `hooks --install/--emit`. Registered in `hammer` TOOLS +
   COMMAND_TO_TOOL (scan/refresh/rebuild/hooks).
3. `GuardGateHook` (exit hook on BACKLOG/READY/PROGRESSING/TESTING/REVIEW/STAGING/DONE)
   rejects transitions with REJECT-severity findings before the physical move.
   `GuardRecordHook` (enter hook) records `--force` bypasses to an append-only
   `events` table and prints a banner — the bypass is never silent.
4. `guard.enforce` / `guard.fail_open` / `guard.staleness_warn_min` config keys.
5. `GUARD_*` codes in `data/errors.json` + `data/hints.json`.
6. F9 fix: `install_hooks` now resolves the COMMON hooks dir via
   `git rev-parse --git-path hooks`, so it works from task worktrees.
7. `tasks move --force` / `-f` is now actually exposed (parser + `cli.move` +
   `commands/move.py` threading); `tasks init-hooks` is wired to `cli.init_hooks`.
8. `tests/test_guard.py` — 18 user tests covering scan determinism, gate rejection
   with folder-untouched assertion, state duplicates, force recording, WARN-only
   remote divergence, self-healing corruption, fail-closed unavailability,
   total ref loss, worktree/common-dir equivalence, duplicate worktrees, gate
   latency, hook install from a worktree.

### Deliberate deviations from plan-guard.md (recorded, not silent)
- R7 decision: counter file is KEPT as the minting backend, guard stays the
  authority (Phase 4 counter retirement deferred — its own task, and R7's
  alternative "git-atomic allocation" would change ID minting under live
  fixtures; not in scope for this task's criteria).
- `worktrees.json` write path retained; guard's `worktrees` table is the git-truth
  view used for anomalies only.
- `GUARD_BRANCH_NOT_MERGED` is NOT re-implemented — existing gates already
  enforce it (`ArchivedCommitHook`, `move.py` ARCHIVED check). Guard absorbs
  nothing from them.
- Worktree anomalies (orphan/missing) are WARN not REJECT: dev fixtures have
  worktrees without matching branches, so rejecting broke the existing suite.
  Marked `shortcut:` in guard_engine.py docstring.
- `GUARD_WORKTREE_MISSING` (WARN) not implemented — mountable, low value.

### Verification
- `tests/test_guard.py`: all pass (run in classes).
- Full suite `python3 -m pytest tests/`: 6 failed / 87 passed / 1 skipped —
  identical to the pre-change baseline (same 6 pre-existing failures).
- `ruff` clean on all files I touched.

### Update — steady-state short-circuit
The first full-suite run showed `test_verdict_is_fast_enough_for_a_gate` failing
(1.08s) because every verdict re-derived everything. Implemented the plan's
step-6 short-circuit: `refresh` compares a sha256 of the live ref set and the
tasks-ref object against the cached signature and, when unchanged, answers from
the index. Measured on this repo (238 refs): cold 0.96s, warm 0.02-0.03s.

### Blockers
- None.
