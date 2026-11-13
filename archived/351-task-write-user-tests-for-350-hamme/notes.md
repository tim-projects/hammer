Task: 351-task-write-user-tests-for-350-hamme

## Status
Implemented on branch `351-task-write-user-tests-for-350-hamme`. Criterion met.

## Change
tests/test_worktree_ownership_user.py (5 tests), driving the hammer CLI in the
--dev fixture repo:
- test_stray_directory_under_the_base_is_reported: a directory nobody registered
  under <dev repo>/.task-worktrees/ is reported by `hammer guard scan` with its
  full path (GUARD_WORKTREE_UNREGISTERED).
- test_doctor_fix_removes_only_the_stray: `tasks doctor --fix` removes the stray
  and leaves the registered worktree intact; the follow-up scan is clean.
- test_a_healthy_worktree_is_not_reported: guard scan does not flag a task whose
  worktree is at the registered path (no false positive).
- test_current_reports_the_worktree_hammer_created: `tasks current <id>` -j
  payload carries worktree_path, and the directory exists.
- test_mount_creates_the_worktree_when_it_is_missing: after
  `git worktree remove --force`, `tasks mount` recreates it and it appears in
  `git worktree list`.

## Verification
- pytest tests/test_worktree_ownership_user.py: 5 passed.
- Full suite + ./hammer check all run before promotion.
