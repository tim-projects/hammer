---
Task: 324-issue-require-explicit-task-id-for-c
---




## Progress

Root cause confirmed: `tasks_ai/task_service.py:76` `get_active_task(None)` returned `items[0]`
of an unsorted `os.listdir(.tasks/progressing)`. `tasks.py` made the id optional
(`nargs='?'`) for `current` and `checkpoint`, so a booted agent that omitted `-id`
silently hit an arbitrary PROGRESSING task and `sync_task_content` (utils.py:65)
wrote that task's record with another branch's commits.

Changes:
- `tasks.py`: `filename` now a required positional for `current` and `checkpoint`
  (undo was already required).
- `tasks_ai/task_service.py`: `get_active_task(None)` returns `(None, None)`; no
  silent pick. Added `processing_candidates()` (the old scan, kept only for the
  error message).
- `tasks_ai/cli.py`: delegate `processing_candidates`.
- `tasks_ai/commands/checkpoint.py`, `current.py`: NO_ACTIVE_TASK error now names
  the PROGRESSING candidates and the id usage.
- `data/errors.json` / `data/hints.json`: NO_ACTIVE_TASK message updated.

Verified in dev (/tmp/.tasks, ids 327 + 329 in PROGRESSING):
- `checkpoint` / `current` / `undo` with no id: argparse usage error, exit 2, zero writes.
- `checkpoint 327`: touch only 327 (gained notes.md; 329 unchanged, no cross-refs).
- `current 327` / `current 329`: correct task each.
- Bad id: error naming both candidates.

Checks: `python3 check.py all --force` passes; ruff clean on changed files.
Test suite running in background; failures need baseline comparison against main.

User tests are owned by child task 325 (Write user tests for 324) per repo convention;
325 branches from main after 324 merges.
## Validation

- `python3 check.py all --force`: all pass. ruff clean on changed files.
- Full pytest (worktree): 6 failed -> after updating test_multiple_checkpoints to
  the new contract: 4 failed.
- Baseline on clean main (55dcf113): the same 4 fail (test_delete_done_task_fails,
  test_regression_check_gate_blocks_staging, test_regression_workflow_cycle,
  test_revert_staging_to_progressing). Tracked as task 326 per repo rule on
  pre-existing unrelated failures.
- test_tasks_modular.py::test_restore_and_undo failed in the full-suite run but
  passes in isolation on the worktree and on main: test-ordering flake, not a
  regression (undo code path untouched by this fix).
- test_multiple_checkpoints updated (was asserting the silent no-id checkpoint);
  now also asserts no-id fails.

## Criteria note

Criterion 1 amended: the CLI no-id path is guarded at argparse (usage error, exit 2,
zero writes). Candidate naming happens on the unresolvable-id path, reachable by
in-process callers. Criterion 6 (user tests) is discharged by child task 325.

## Tests (final)

tests/test_require_task_id.py added, modeled on tests/test_robustness.py's
setUp (symlinked hammer), so it exercises the working-tree branch code:

- test_no_id_is_rejected: checkpoint/current/undo without id all fail
- test_no_id_writes_nothing: no-id commands leave both records byte-identical
- test_explicit_id_hits_only_that_task: checkpoint <id> touches only that record
- test_current_with_id_reports_that_task: current <id> reports the right task
- test_unresolvable_id_is_rejected: bad id fails for all three commands

5/5 pass on the branch; the same commands succeed without id on main (verified
in a fixture), so these are genuine regression tests. test_multiple_checkpoints
(updated to the new contract) also passes: 6/6.

Note on the harness: tests/hammer_test_base.py clones the repo and force-checks-out
origin/main, so HammerTestBase-based tests cannot see branch code; that is why the
tests follow the test_robustness.py symlink pattern.