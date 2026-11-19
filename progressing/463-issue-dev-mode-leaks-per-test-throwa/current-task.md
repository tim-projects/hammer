# Task 463 — progress log (final)

## What landed
- `tasks_ai/context.py`: `ProjectContext.reclaim_stale_dev_dirs(tasks_path, now=None)` —
  sweeps harness prefixes (`hammer_tasks_`/`hammer_test_`/`hammer_remote_`) under the temp
  dir with mtime older than HARNESS_STALE_AFTER (1 day), never the live store or its repo;
  called on the cold path in `_ensure_dev_repo` (right before a new clone).
- `tests/test_dev_repo_reclamation.py` (3 tests): stale swept / fresh kept / live kept /
  foreign prefixes untouched, plus addCleanup-covers-setUp-failure. Duplicate tests dropped:
  `tests/test_temp_cleanup.py` (commit 5662202f, in-flight) already covers loud failure and
  nested zero-net-growth.
- Task 473 (issue, p1) created for the 3 pre-existing full-suite order-flakes.

## Evidence
- Branch full suite x3: only pre-existing flake failures (dev-isolation dev-init, temp-cleanup
  nested growth, store-writes race) — no new classes; the flaky dev-isolation test also fails
  on unmodified main in file context. The sweep is innocent there (debug-logged: zero
  candidates, test still failed).
- The sweep's real effect: run 1 reclaimed the ~4.5GB historical orphan mass (1790 dirs →
  /tmp 87M); ENOSPC no longer occurs after clearing. Pre-fill criterion verified via the
  500-seeded-dir run.
- Lint PASS; targeted files green (dev_repo_reclamation, init_backup, lazy_task_creation,
  dev_store_guard, dev_write_audit, store_concurrency: 24+15+9 passed across runs).

## Notes for reviewers
- One-time non-reproducible flake in my own nested-growth test during the first branch suite
  run; the test was dropped as a duplicate of test_temp_cleanup.py's equivalent.
