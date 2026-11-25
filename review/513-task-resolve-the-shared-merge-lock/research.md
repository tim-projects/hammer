Research pass for 513 (read-only, 2026-11-24). Sources: repo.py, tasks_ai/utils.py,
tasks_ai/git_service.py, tasks_ai/context.py, tasks_ai/guard_engine.py,
tests/test_merge_lock_guard.py, .tasks records for 483/489, live git state.

1. Lock construction: `tasks_ai/utils.py:34-55` — `merge_lock(repo_root)` joins
   `repo_root/.git/hammer-merge.lock` and `os.makedirs(..., exist_ok=True)`.
   Reentrant per-thread via `_merge_local.depth`; kernel-released flock.
2. Callers disagree on the root: `repo.py:346` passes `repo_root()` (the invoked
   git top-level = worktree when run from a linked worktree); `git_service.py:431`
   passes `self.context.main_repo_root` (correct). Same-intent, two different lock
   files => the shared lock is not actually shared.
3. Linked worktree layout: `.task-worktrees/489-task-key-repo-merge-plumbing-to-the/.git`
   is a regular file (`gitdir: .../.git/worktrees/489-...`) -> makedirs raises
   FileExistsError (reproduced in the 489 blocker notes, commit a5b..? see
   .tasks/pr/489-.../current-task.md).
4. git behavior verified on this machine:
   - `git -C <worktree> rev-parse --git-common-dir` -> `/home/vscode/git/tasks-ai/.git` (absolute)
   - `git rev-parse --git-common-dir` (main) -> `.git` (relative)
   - `git -C <worktree> rev-parse --absolute-git-dir` -> `.git/worktrees/489-...` (per-worktree; WRONG for a shared lock)
5. House pattern already exists, reuse it: `tasks_ai/context.py:123-136`
   (ProjectContext._get_main_repo_root) and `guard_engine.py:171-180`
   (GuardEngine._main_repo_root / _resolve_cache_dir) both run --git-common-dir
   from the caller cwd, join relative output against abspath, normpath.
6. Test precedent: `tests/test_merge_lock_guard.py` builds REAL git repos in
   tempdirs (`setUp`, :23-47) with a `git()` helper (:16-19) — add a
   `git worktree add` case there.
7. State check: no `provisioning` ref exists anywhere; 489-PR unmerged; task 489
   is in PR with RegressionCheck PASSED; no stale `hammer-merge.lock` on disk.
8. Related decisions: D6 in plan-hammer.md (flock on funnel merges, store_lock
   pattern) is unchanged — this bug is the old helper never honoring it from a
   worktree. 483 implemented the lock at `<main_repo_root>/.git/hammer-merge.lock`.
9. Sequencing: 513 must land on main before 489's funnel merge
   (`repo merge 489 provisioning -y`), which runs from 489's worktree after
   syncing main in.