---
Task: 413-issue-promotion-merge-conflict-halts
---


- Progress:

## Fix (2026-11-12)

Root cause: `tasks_ai/git_service.py` `merge_branches` raised a bare
`RuntimeError` on merge failure. `move.py` only catches `PipelineMergeConflict`,
so the MERGE_CONFLICT code/hint (data/errors.json:34, data/hints.json:34) was
unreachable for promotions, no `merge --abort` ran (main repo left mid-merge on
the target branch, since checkout happens before the merge), and the RuntimeError
escaped tasks.py as a traceback.

Changes:
- `merge_branches` (tasks_ai/git_service.py:353-360): on merge failure run
  `merge --abort` then raise `PipelineMergeConflict(src, target)`, mirroring the
  healthy `sync_worktree` path (tasks_ai/git_service.py:442-444). No new
  abstraction: reuses the existing exception the CLI already routes.
- `move_logic` (tasks_ai/commands/move.py:166-167): `--force` (which skipped the
  merge entirely at move.py:157) now logs an explicit warning that the pipeline
  merge is skipped. Decision taken: keep the bypass, warn. Routing forced moves
  through the check would change `--force` semantics (it is also used to bypass
  gate failures) and was not requested.
- Regression test `tests/test_tasks.py::TestTasksAI::
  test_conflicting_promotion_halts_with_merge_conflict` (scratch dev repo,
  conflicting edit of README.md on the pipeline branch): asserts the CLI renders
  Merge conflict + full hint, no JSON decode error / traceback, no MERGE_HEAD and
  no unmerged paths afterwards, and the task stays in progressing.

Verification: pytest tests/test_tasks.py (+ mount_sync, default_branch,
hooks_default_branch, all_transitions) 51 passed; full remaining suite 227 passed,
1 skipped; ./hammer check lint/format/typecheck/debug green.

Not fixed / follow-up:
- `sync_pipeline` (git_service.py:314) calls merge_branches but now can raise
  PipelineMergeConflict with no caller today (no CLI entry point reaches it).
  Wrapping it would be dead code.
- After a failed promotion the main repo stays checked out on the target
  pipeline branch (same as the healthy worktree path leaves HEAD); that matches
  existing behaviour and is not part of the issue.