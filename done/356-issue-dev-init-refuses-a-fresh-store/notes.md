# Task 356: Dev init refuses a fresh store

Status: fix implemented, tests added, ./hammer check all green.

## Root cause (confirmed)
- `TasksCLI.__init__` (tasks_ai/cli.py, dev branch) pre-creates the store dir
  for every dev command; `init()`'s dev branch then tested bare existence, so
  a fresh `--dev init` always refused AND left a plain non-git directory.
- Every later dev command degraded silently: store_is_git() false ->
  commit_task_paths() returns without committing; writes land on disk only.

## Fix
tasks_ai/cli.py `init()` dev branch: a store is initialized only by content
init itself writes -- `.git` in the store, or task records
(`_tasks_directory_has_data`). Fresh path -> initialize; real store ->
refuse without --force, reset with --force (records found are kept intact on
refusal, backup+reset only on --force).

## Verification
- Fresh `HAMMER_DEV_TASKS_DIR=/tmp/... --dev init` -> exit 0, store is a git repo.
- Second init -> exit 1 "already initialized"; `--force` -> resets.
- Records-only store (no .git) -> refused, .task_counter kept; `--force` resets.
- create/checkpoint against a freshly init'd store -> commits visible in
  `git -C $store log` (Add task / Bump counter / Cp).
- tests/test_dev_isolation.py: new TestDevInitOnAFreshStore (4 tests) pins all
  of the above; full suite 10/10 OK; ./hammer check all (lint/test/typecheck/
  format) all pass.

## Notes / debt
- Non-dev init still checks existence first but is not affected: the CLI only
  pre-creates the store dir in dev mode.
