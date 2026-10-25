---
Task: 87-task-implement-worktree-based-task
---

- Progress: 

## Status

Implementation complete and verified. All key tests pass; lint/pyright clean for this task's
changes. Two pre-existing issues documented in new tasks (241, 243) — not fixed here because
they predate 87 (verified identical against HEAD b944cf4).

## Work completed

- Created `tasks_ai/worktree_manager.py` (`WorktreeManager`: create/list/remove/prune,
  manifest `.tasks/worktrees.json`)
- Wired `WorktreeManager` into `GitService` as `cli.git.worktrees` (lazy-loaded)
- Added worktree logging to `GitService._handle_command_logging`
- Refactored `create.py` to create worktrees via `cli.git.worktrees.create_task_worktree()`
  instead of `git checkout -b`
- Created `commands/mount.py` for `tasks mount <id>`; wired into `tasks.py` CLI (subparser +
  dispatch) and `hammer` (`COMMAND_TO_TOOL`), added `mount()` to `TasksCLI` in `cli.py`
- Renamed/refactored 4 branch hooks in `pipeline_hooks.py` to worktree equivalents
  (`WorktreeSyncHook`, `WorktreeCheckHook`, `WorktreeExistsHook`, `WorktreeSyncOnExitTestingHook`)
- Updated `ArchivedCommitHook` to remove worktree only on ARCHIVED with `force=True` after
  merge confirmation (`cli.git.is_merged()`)
- Updated `MainBranchProtectionHook` to warn if not in task worktree
- Updated hook imports/registrations in `cli.py`
- Updated `PipelineService.validate_gate` for worktree-aware messaging
- Updated `GitService.merge_branches` to use `main_repo_root` for pipeline branch operations
- Updated `GitService.promote_task` to commit worktree changes before transition, use
  worktree path for status checks
- Updated `GitService.demote_task` to sync through worktree if it exists
- Updated `GitService.is_merged` and `branch_exists` to accept `cwd` parameter
- Updated `commands/move.py` ARCHIVED check to use task metadata `Br` (fixed `IndentationError`)
- Rewrote `commands/cleanup.py` to prune worktrees + clean merged branches using `main_repo_root`
- Rewrote `commands/unarchive.py` to mount worktree instead of checking out branch
- Updated `repo.py` `cmd_demote` to use worktree-aware git operations
- Updated reconcile methods in `cli.py` to use `main_repo_root`/`context`
- Added worktree errors to `data/errors.json` (`WORKTREE_NOT_FOUND`, `WORKTREE_MERGE_CONFLICT`,
  `WORKTREE_MISSING_AUTO_DEMOTED`, `CONFLICT_DETECTED`) and `data/hints.json`
- Updated `help_text.py` with worktree workflow docs and `tasks mount <id>`; updated `AGENTS.md`

## Fixes made during verification

1. `tasks_ai/pipeline_hooks.py` — `MainBranchProtectionHook` blocked `tasks move` whenever the
   current branch was the default branch. This broke the worktree model, where `tasks move` is
   meant to run from the main repo (the pipeline engine handles worktree context internally).
   Now transitions are allowed from the default branch when the task has its own `Br` branch;
   protection still fires when there is no task branch.
2. `tests/test_tasks.py::test_full_lifecycle` — was missing the `move <issue_file> PROGRESSING`
   step, so the issue transitioned READY -> TESTING and failed with "Forbidden transition".
3. `tasks_ai/git_service.py` — worktree log message mis-parsed `git worktree add -b <branch>
   <path>` (the fallback form used whenever a task branch does not yet exist), logging
   "Added worktree at '-b'". Both forms end with the path, so the log now uses `args[-1]`.
4. `tasks_ai/pipeline_hooks.py` — restored `# noqa: SIM102` directives that were dropped when
   the branch hooks were renamed to worktree equivalents (they existed in HEAD).
5. `.gitignore` — added `.task-worktrees/`. Without it every task worktree (a full repo copy at
   `<main_repo>/.task-worktrees/<branch>`) showed up as untracked noise in `git status`.
6. `tasks_ai/validation.py` — `validate_path` allowed only paths under `cli.root`. Running any
   task command from inside a task worktree failed with
   "Path outside repository: <main_repo>/.tasks/backlog/<task>", because task metadata always
   lives in the main repo's `.tasks/` while `cli.root` is the worktree. `find_task` therefore
   returned nothing and `show`/`list`/`mount`/`move` all failed from inside a worktree.
   Fixed by allowing the main repo root alongside the worktree root.
   Found by manual verification (criterion 4), not by tests: both `--dev` mode and any path
   under `/tmp` short-circuit `validate_path`, so no existing test could reach it.

## New tests: tests/test_worktree_system.py (4 tests, criterion 10)

Runs **without** `--dev` and with the repo created under `/var/tmp`, so the production
`validate_path` path is actually exercised. The repo root helper skips the module if no
writable non-`/tmp` dir exists — a silent pass would be worse than no test.

- `test_worktree_created_with_manifest_entry` — worktree dir, `git worktree list` entry,
  branch, and `.tasks/worktrees.json` manifest entry all agree (criteria 1, 2)
- `test_task_operations_resolve_from_inside_worktree` — `show`, `list`, `mount` and a
  pipeline `move` succeed from inside the worktree, plus `show` from the main repo
  (criteria 4, 9). Verified as a real regression guard: reverting the validation.py fix
  makes it fail with the original "Path outside repository" error.
- `test_mount_recreates_removed_worktree` — `mount` recreates a removed worktree (criterion 3)
- `test_worktree_removed_on_archived` — full lifecycle to ARCHIVED; worktree dir,
  `git worktree list` registration and manifest entry are all removed (criterion 7)

## Criteria verification (evidence)

1. WorktreeManager create/list/remove/prune — methods present in
   `tasks_ai/worktree_manager.py` (create_task_worktree, list_worktrees,
   remove_task_worktree, prune_worktrees); covered by new tests.
2. Manifest persisted — `.tasks/worktrees.json` verified live for tasks 241-246, matching
   `git worktree list` exactly; asserted in new tests.
3. `tasks mount <id>` — `tasks_ai/commands/mount.py`; verified live (mount 2, mount 243)
   and by `test_mount_recreates_removed_worktree`.
4. Task ops resolve from inside a worktree — found a real bug and fixed it; regression test
   verified to fail without the fix.
5. Worktree-to-main merge — `GitService.merge_branches()` runs from `main_repo_root`;
   exercised by the passing promotion/merge suites.
6. Conflict detection — `WORKTREE_MERGE_CONFLICT` in `data/errors.json`; `WorktreeSyncHook`
   aborts the merge (`merge --abort`) and raises on conflict.
7. Worktree removal on ARCHIVED — verified end-to-end in a real non-dev repo
   (`/tmp/kilo/nd`): worktree existed before, gone after, manifest entry removed; also
   asserted by the new test.
8. Backward compatibility — the branch-style flows in `tests/test_robustness.py`
   (manual `git checkout -b`, merges, etc.) still pass: 44/48 with the 4 pre-existing
   failures documented in task 245.
9. Pipeline gates from within a worktree — `move READY` from inside a worktree succeeds;
   5 review-gate integration tests pass.
10. User tests written and passing — `tests/test_worktree_system.py`, 4/4 pass.
11. Documentation — `AGENTS.md` (10 worktree mentions), `tasks_ai/help_text.py`.

## Test results (all pass)

- `tests/test_tasks.py::test_full_lifecycle` — pass
- `tests/test_all_transitions.py` — pass
- `tests/test_pairing.py` — pass
- `tests/test_audit_verify_integration.py` — 5/5 pass (incl. `test_staging_blocked_without_regression_check`)
- `tests/test_audit_verify.py`, `tests/test_backlog_to_rejected.py` — pass
- `tests/test_tasks_modular.py` (4), `tests/test_cli_endpoints.py` (4), `tests/test_error_reporting.py` — pass
- `tests/test_artifact_healing.py`, `tests/test_git_hook_restrictions.py`, `tests/test_init_backup.py` — pass
- `tests/test_robustness.py` — 44/48 pass. The 4 failures
  (`test_regression_check_gate_blocks_staging`, `test_regression_workflow_cycle`,
  `test_revert_staging_to_progressing`, `test_delete_done_task_fails`) were each verified
  pre-existing by re-running them at HEAD b944cf4 with `git stash` — identical
  "Regression check not passed (Rc flag not set)" failures. Recorded as task 245.
- `tests/test_robustness_bugfix.py`, `tests/test_security.py`, `tests/test_repo.py` — pass
- `tests/test_dev_mode.py` — skipped upstream (`unittest.skip('Diff generation needs debugging')`)

## Lint / typecheck

- `ruff check tasks_ai/ tests/`: 11 errors remain, ALL pre-existing at HEAD (diffed against
  `git stash` baseline; only line numbers shifted). Zero introduced by this task. Recorded as
  task 243.
- `npx pyright tasks_ai/`: 0 errors, 0 warnings.

## Pre-existing issues found (NOT fixed here — new tasks created)

- **Task 241 — fast-track gate bypass (issue).** `PipelineService.validate_gate`
  (`tasks_ai/pipeline.py:77-82`) returns True immediately for REVIEW/STAGING/DONE when
  `git.is_merged(branch, "main")` is true, skipping the checkboxes, regression_check,
  audit_integrity and mandatory_verification gates. `GitService.is_merged`
  (`tasks_ai/git_service.py:107`) uses `git merge-base --is-ancestor branch origin/main`,
  falling back to local `main` when no remote exists. A freshly created worktree branch points
  at the same commit as main, so `--is-ancestor` succeeds and the branch is reported merged.
  Verified empirically in `/tmp/kilo/fttest`: branch with zero new commits => exit 0 (merged);
  branch with commits => exit 1 (not merged). Identical logic exists at HEAD — not a 87
  regression.
- **Task 245 — four pre-existing test failures.** `tests/test_robustness.py`:
  `test_regression_check_gate_blocks_staging`, `test_regression_workflow_cycle`,
  `test_revert_staging_to_progressing`, `test_delete_done_task_fails`. Each verified
  identical at HEAD (re-run under `git stash`). Cause: task 239's verifiable patch review gate
  requires review/audit/regression-check before STAGING/DONE, and these older tests never run
  that flow. Repo gate config sets `repo.test` to `/bin/true`, so they do not block promotions.
- **Task 243 — pre-existing ruff lint errors.** 11 errors across `audit.py`,
  `commands/audit.py`, `commands/create.py`, `commands/doctor.py`, `pipeline_hooks.py` (BLE001).
  Verified present at HEAD. Repo gate config `.tasks/config.yaml` sets `repo.lint` to `/bin/true`,
  so these do not block promotions today.

## Shortcut notes

- `shortcut: the full 48-test robustness suite was executed in batches, not one process;
  all 48 tests ran at least once. Remaining risk: none known.
