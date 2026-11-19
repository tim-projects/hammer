Observed on `a5b971e8` main and on task 463's branch (identical in both):
1. `tests/test_dev_isolation.py::TestDevInitOnAFreshStore::test_store_records_without_a_git_repo_are_refused_not_clobbered`
   — fails when run inside the file (1 failed/9 passed on UNMODIFIED main); passes standalone.
   Two observed failure modes: TASKS_CLONE_FAILED (clone "No such file or device") and
   "a refused init destroyed the task records it found".
2. `tests/test_temp_cleanup.py::TempCleanupTest::test_init_backup_suite_leaves_no_hammer_temp_paths`
   — nested-pytest zero-growth test; failed in one full-suite run, passes standalone. The
   same flake hit the equivalent test written for task 463 (dropped as duplicate).
3. `tests/test_store_writes.py::TestStoreCommitsAreScopedPerCommand::test_concurrent_unlink_and_checkpoint_stay_scoped`
   — race-dependent store commit scoping: another task's paths leak into this command's commit
   ("the race must produce exactly one commit per command").
Common shape: all three depend on state left by earlier tests (or on /tmp pressure), so the
suite result is not reproducible.
