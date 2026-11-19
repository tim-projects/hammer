# Task 463 — progress log

## Finding (corrects the task's original premise)
Completed runs do NOT leak: name-diff experiments (test_init_backup, test_backlog_to_rejected,
test_lazy_task_creation) showed zero net /tmp growth; the harness already registers
addCleanup for every dir (hammer_test_base.py setUp). The 388 leftover dirs are orphans of
interrupted runs / older code / manual sessions, and nothing ever reclaims them: /tmp only
grows (observed 1790 dirs, tmpfs 100%), after which every suite run dies with ENOSPC and
masks real failures (173 fake failures vs the true 4 order/disk flakes).

## Change
- `tasks_ai/context.py`: `ProjectContext.reclaim_stale_dev_dirs(tasks_path, now=None)` —
  sweeps harness prefixes (`hammer_tasks_`/`hammer_test_`/`hammer_remote_`) under the temp
  dir with mtime older than HARNESS_STALE_AFTER (1 day), never the live store or its repo.
  Called on the cold path in `_ensure_dev_repo` (right before a new clone).
- `tests/test_dev_repo_reclamation.py` (new): stale swept / fresh kept / live kept /
  foreign prefixes untouched, plus a zero-net-growth test that runs a base-harness test
  file in a subprocess and name-diffs /tmp.

## Evidence
- New file: 3 passed (4 consecutive runs; first run showed one non-reproducible flake in
  the subprocess test, 3/3 green after — noted, watch it).
- Targeted: test_init_backup + test_lazy_task_creation (9 passed), test_dev_store_guard +
  test_dev_write_audit + test_store_concurrency (15 passed).
- One-off observation during the run: the sweep removes the pre-existing day-old orphans;
  /tmp shall now stay bounded after this merges.

## Remaining
- Full suite via the TESTING gate (4 known order/disk flakes expected, tracked as Task 54
  in the upgrade-work plan).
