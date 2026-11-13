# 326 — Root causes of the four robustness failures

Status: all four pass on main today, in isolation and in the full suite.
Verification runs (2026-11-13, commit a0546a49):

- isolation: `python3 -m pytest tests/test_robustness.py -q -k 'test_delete_done_task_fails or test_regression_check_gate_blocks_staging or test_regression_workflow_cycle or test_revert_staging_to_progressing'` → 4 passed
- full suite: `python3 -m pytest tests/ -q -p no:randomly` → 278 passed, 1 skipped, 270 subtests passed (1337s)

## The failures (reproduced on 55dcf113 in a throwaway clone, /tmp/old-main-repo)

4 reported, 3 reproduced in isolation; the 4th (`test_revert_staging_to_progressing`)
passes on 55dcf113 in isolation and is only reported as failing there.

Root cause is one bug with three symptoms: at 55dcf113 the task store
(`.tasks/<state>/<task>`) lived **inside the code repo worktree** and the old flow
committed store files into task branches (the `git add -f .` bleed, fixed later by
the store-separation work). Any `git checkout` / `git merge` the tests themselves
perform therefore rewrote the store from the branch copy, so the store and the git
history diverged.

1. **test_delete_done_task_fails** — `move <task> TESTING` failed with
   `UNFINISHED_CHECKBOXES` even though `complete_criteria()` had marked every
   criteria.md. Instrumented the gate (has_unfinished_checkboxes) and saw the file
   the gate reads return to its unmarked content after the test's own
   `git checkout -b testing; git merge <branch>; git checkout main` steps. Git
   itself confirms the collision:
   `error: untracked working tree files would be overwritten by checkout: .tasks/progressing/<task>/criteria.md`.

2. **test_regression_check_gate_blocks_staging** — the STAGING move was expected to
   fail with an error containing "regression". Instead the checkbox gate fired
   first on the clobbered store, so the test asserted
   `'regression' not found in 'task contain unfinished checkbox (- [ ]).'`. Same root
   cause; the regression gate never got to run.

3. **test_regression_workflow_cycle** — `move <task> PROGRESSING` (demotion after
   REVIEW) exited **rc=0 with empty stdout and stderr**. `run_cmd` then hit a JSON
   decode error. The silent exit is the CLI's "already on <state>" / forbidden-transition
   path returning without ever calling finish(), reached because the store's state
   folder and the task record disagree after the clobber.

4. **test_revert_staging_to_progressing** — passes on 55dcf113 in isolation, in this
   run and in the issue's repro. Reported as failing on clean main; no longer
   reproducible anywhere, and the related full-suite ordering flake
   (`test_tasks_modular.py::test_restore_and_undo`) is also green in the 278-passed run.

## Why main is green

The store now lives outside the code repo (`.tasks-repo` + `tasks` branch), so
pipeline transitions operate on the shared store and the tests' branch operations
no longer rewrite task state. Demotion and the already-on-state path emit JSON
errors instead of exiting silently. No code change was needed for this issue:
the four tests pass on main as merged; this issue is closed as a
documentation + verification pass.

## Residual notes

- `/tmp/old-main-repo`, `/tmp/old-main-dbg`, `/tmp/dem-repro` are throwaway
  investigation clones outside the repo; safe to delete.
- Unrelated leftovers seen during discovery: orphaned worktrees/branches for task
  ids 407/408/409 (no task records, no commits, no work) — separately reported,
  not part of this fix.
