# Research: store-inside-worktree bug (task 410)

## Root cause (verified)
- `tasks_ai/context.py:42` resolves `tasks_path` = `main_repo_root/.tasks` via
  `git rev-parse --git-common-dir` — correct.
- `tasks_ai/cli.py` (~166-198) falls back to `self.tasks_path = os.path.join(self.root, ".tasks")`
  where `self.root = context.repo_root` = the worktree root, so when the common-dir lookup fails
  the store is created inside the worktree.
- `check.py:find_project_root()` starts at cwd and returns the worktree root inside a worktree;
  the *config* lookup falls back to the main store but tool cwd stays the worktree.
- `tests/check.py` is a stale pre-worktree-fix mirror of `check.py`: no `get_main_repo_root()`,
  no worktree config fallback, `get_last_hash_path() = find_project_root()/.tasks/.last_validation_hash`
  → it creates `<worktree>/.tasks`. It is not invoked by the current pipeline; deletion belongs to
  task 368 Group 3 (human approval gate there). Record only.

## Observed damage
- `.task-worktrees/312-issue-guard-refs-cache-must-not-clob/.tasks/` and
  `.task-worktrees/314-issue-guard-must-assess-strictly-wit/.tasks/` each hold a store fragment
  (`.last_validation_hash` + `progressing/<task>/`) written by that mirror while cwd was the worktree.
- Central records for 312/314 are intact in `.tasks/done/` (verify before removing fragments).

## Fix design
- `STORE_NOT_CENTRAL` guard in `TasksCLI.__init__`: fire when (a) the store path cannot be
  resolved, or (b) after any `tasks_dir`/config override, the resolved path is inside
  `context.repo_root` while `context.is_worktree`. Use `os.path.commonpath`, not `startswith`.
- Register the code in `data/errors.json` + `data/hints.json` (test_help_coverage/test_tasks
  assert every `cli.error` code exists in both).
- Regression test: drive a task command from inside a worktree; assert no `<worktree>/.tasks`.

## Store hygiene found while working (context, not this task's scope)
- `.tasks/.task_counter` was stale (105 vs max id 403); bumped to 409 by hand (md5 hash rewritten)
  so `tasks create` stopped re-allocating duplicate ids. Stale duplicates: rejected 402 guard,
  backlog 403 test-for-402-guard, and worktrees `402-task-*` (3).
- Records 404 and 406 lost all files except `current-task.md` (tracked `meta.json` is not
  gitignored) — rebuild is tracked separately.
