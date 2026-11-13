
- Progress: 

## Implementation (task 338)

Model chosen: **isolate, do not refuse** (tech.md option 2). `--dev` now binds every
git operation to a throwaway repo keyed on the dev store, so the repo the CLI is
invoked from is never written to.

### Changed

- `tasks_ai/context.py`: in dev mode `repo_root`/`main_repo_root` (and therefore
  `WorktreeManager.worktrees_base`, `GitService.run` default cwd, the guard cache
  dir, `audit.generate_file_patches`) resolve to `<HAMMER_DEV_TASKS_DIR>-repo`,
  created once as a local clone of the invoked repo with its local branches
  mirrored. `DevRepoUnavailable` is raised instead of falling back.
- `tasks_ai/cli.py`: catch `DevRepoUnavailable` and emit `DEV_REPO_UNAVAILABLE`
  (names the command and "run ... WITHOUT --dev"); refuse `tasks save` in dev
  (`DEV_COMMAND_REFUSED`).
- `guard.py`: `guard --dev` assesses the same throwaway repo via
  `ProjectContext(dev=True)` instead of the invoked repo.
- `tasks_ai/git_service.py`: never push in dev (store push and `merge_branches`
  push would move real refs); `is_merged` assesses the dev repo locally (its
  origin is only a snapshot of the repo it was cloned from).
- `tasks_ai/pipeline.py`: the main-divergence gate is skipped in dev, where local
  main is always ahead of the snapshot origin.
- `data/errors.json`, `data/hints.json`: the two new message templates.
- `AGENTS.md`: --dev guidance now states what actually happens.

### Tests

- New `tests/test_dev_isolation.py`: repo byte-identical after a dev
  create/mount/checkpoint cycle; dev worktree/branch live only in the throwaway
  repo; dev repo reused across invocations; dev create at a colliding id blocks
  only the dev move while the real guard verdict stays PASS; unusable dev repo
  path refuses with a clear error; `save` refused in dev.
- `tests/test_tasks.py`: pipeline-branch simulations now target the dev repo
  (the fixture repo is the "main" repo dev mode must not touch).
- `tests/hammer_test_base.py`: shared `dev_repo_path` / `project_tasks_ai`
  helpers, and tearDown removes the dev repo.

### Notes / debt

- `tasks --dev init` still appends `/.tasks.backup/` to the *invoked* repo's
  `.gitignore` (`_ensure_tasks_backup_gitignored`); a config line, not a ref.
- `cli_engine.py` still hardcodes `/tmp/.tasks`; it is dead code (`tasks.py`
  imports `tasks_ai.cli`), left alone.
- The dev repo keeps `origin` = the invoked repo, so `git fetch` in dev reads it
  (read-only). Pushes are the only writes blocked explicitly.