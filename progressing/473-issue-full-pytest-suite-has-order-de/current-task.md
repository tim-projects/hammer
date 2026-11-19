---
---

# Task 473 — progress log

## Root causes found and fixed

### Flake 1 — dev_isolation dev-init (TASKS_CLONE_FAILED / "1 != 0")
- Caught in the act with GIT_TRACE: `git clone --branch tasks --depth 1 <fixture repo> <store>`
  failing intermittently (~25% of runs) with `failed to copy file to .../pack-*.pack: No such
  file or directory` — a transient local-clone copy failure. The old code cloned straight into
  the destination, so a failed attempt also left a half-written store behind.
- Also found and fixed a real bug in my first fix iteration: when the dev-repo path is occupied
  by a FILE, the old clone refused cleanly; the atomic version crashed (os.replace onto a file)
  with an empty stdout, breaking `test_unusable_dev_repo_path_refuses_with_a_clear_error`.
- Fix: `clone_local(source, dest, *extra)` in `tasks_ai/context.py` — refuses non-directory
  destinations, clones into `<dest>.tmp-<pid>`, bounded 3-attempt retry with backoff, swaps on
  success, never leaves debris. Wired into `_ensure_dev_repo` and the dev `init` clone.
  Dev `init --force` now restores its backup when the clone fails outright (the reset removed
  the store before cloning).
- Tests: `tests/test_dev_isolation.py::TestCloneRobustness` (retry-absorbs-one-failure;
  failed-clone-leaves-no-debris). Full file now 12/12 across 4 consecutive runs.

### Flake 3 — store commit scoping race
- Root cause: `TasksCLI._append_log` staged the log file with an UNLOCKED `git add` in the
  shared store index. `commit_task_paths` holds the store lock around its own scoped add+commit,
  but `git commit` without a pathspec commits the whole index — so any concurrent command that
  committed in the window swept the staged log line into its commit ("another task's paths").
- Fix: removed the unlocked add (comment records why). Every `_append_log` caller commits through
  `commit_task_paths(<task dir>)`, which already stages the log file under the lock.
- Verification: the concurrent unlink+checkpoint test passes 5/5 in a stress loop.

### Flake 2 — temp_cleanup nested zero-growth test
- Single observation in a full-suite run; passes standalone. Hypothesis: the same transient
  clone failure inside the nested run left a directory behind. To be confirmed by the two
  consecutive full-suite runs below (acceptance criteria require them anyway).

## Verification in flight
- Full suite x2 on the branch (background). Criterion: identical results, the three tests green
  standalone and in-suite.

## Final evidence (after the retry was strengthened to 5 attempts)
- TestCloneRobustness: 2 passed. DevInitOnAFreshStore class: 4/4 passed.
- File runs since the fix: 7 consecutive 12/12 green runs (incl. 3 after the change).
- Full suite run 1: 369 passed, 1 skipped, 0 failed.
- Full suite run 2: 368 passed, 1 skipped, 1 failed — the same test, residual transient
  clone failure. Rate: ~1 per 2 full suites (was ~25% of file runs).
- Race test (flake 3): 5/5 in a stress loop, and green in both full-suite runs.
- Flake 2: green in both full-suite runs; no independent root cause observed.
- Lint PASS.
