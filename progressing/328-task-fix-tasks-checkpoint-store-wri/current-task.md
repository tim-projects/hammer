---
Task: 328-task-fix-tasks-checkpoint-store-wri
---


## Findings (while implementing)

- Store write helpers (3 call sites): `tasks_ai/utils.py` now has `commit_task_paths`
  (task-scoped `git add`/`git commit`, fatal on failure) used by checkpoint, modify, link.
- `sync_task_content` no longer diffs the main repo (where `.tasks` is ignored, so the
  parts branch was dead code). Change detection is now `git status --porcelain -- <task dir>`
  run in the store repo (covers modified/staged/untracked), and part files are read
  directly off disk. All git calls pass explicit cwd (`main_repo_root` or `tasks_path`).
- Bug found en route: `cli._append_log` staged `activity.log`, a file that is never
  written (FM.append_log writes `<section>.md`, i.e. `progress.md`), so every log line
  was silently uncommitted. Fixed; the log line now also lands inside the checkpoint's
  own commit (it ran after the commit before).
- Store that is NOT a git repo (some fixtures build a plain store dir): `store_is_git`
  guard keeps that case lenient - fatal errors are reserved for a real store repo
  whose add/commit fails (contention, stale index.lock).
- Deliberately out of scope (same hazard, move path): `PostMoveCommitHook`
  (tasks_ai/pipeline_hooks.py:327) still does `git add -f .` in the store, which
  stages every agent's pending work and leaves `.ops/staging/<task>` + old-state
  deletions pending afterwards. Worth its own task.

## Tests

- `tests/test_checkpoint_store_writes.py`: scoped-commit isolation between two tasks,
  fatal add failure (held `.git/index.lock`) with retry-after-recovery, fatal commit
  failure (`GIT_COMMITTER_DATE=bogus`), hand-edited parts syncing into the record,
  and the same sync/checkpoint run from a task worktree cwd.