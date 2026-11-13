Research pass on task 404 (full pytest baseline), repository /home/vscode/git/tasks-ai.

Bare `pytest` in the project root does not run a single test: collection aborts on the
tracked root-level scratch file test_is_merged.py (line 8 calls
tasks_ai/git_service.is_merged with a MagicMock main_repo_root, so
subprocess.run raises FileNotFoundError). Root scratch files involved:
test_create_logic.py, test_is_merged.py, test_pairing_logic.py, test_regex.py — all four
are named in task 368's Group 1, which carries a binding per-group human approval gate
for deletion, so they cannot be removed here.

Constraining the run to the real suite (`pytest tests/ -q`, 252 collected) gives
39 failed / 212 passed / 1 skipped / 270 subtests passed in 909s:
- tests/test_all_transitions.py::test_transitions
- tests/test_default_branch.py: test_promotion_resolves_master,
  test_worktree_sync_merges_master, test_promotion_fails_with_actionable_error
- tests/test_dev_write_audit.py: test_dev_artifacts_live_under_the_dev_roots,
  test_full_dev_workflow_writes_nothing_outside_the_dev_roots
- tests/test_guard.py::test_clean_task_passes_gates
- tests/test_require_task_id.py: test_explicit_id_hits_only_that_task (FileNotFoundError,
  tests/test_require_task_id.py:93), test_no_id_writes_nothing
- tests/test_robustness.py: 9 tests
- tests/test_store_concurrency.py: 2 tests (one also hits TypeError, subprocess.run with
  a None argument)
- tests/test_store_writes.py: 9 tests
- tests/test_tasks.py: 9 tests
- tests/test_worktree_system.py::test_worktree_removed_on_archived

Dominant root cause: the READY -> PROGRESSING research gate (ResearchGateHook in
tasks_ai/pipeline_hooks.py, registered tasks_ai/cli.py:63, landed on main as 45c3a128
"READY exit gate requires a recorded research pass"). ~30 of the 39 failures are suites
that create a task and move it straight to PROGRESSING without first recording research,
so the move returns RESEARCH_REQUIRED and every later assertion in the suite fails
because the task file never reached the expected folder. The fix is test-side: seed the
research before the move.

Second cause: tests/test_require_task_id.py:93 and tests/test_robustness.py:383 raise
FileNotFoundError on a file under .tasks/testing/<task>.

Blockers found while measuring:
- Task 404's own Bl entry is 402-task-fix-hammer-check-all-so-valida (state PROGRESSING),
  and BlockerCheckHook (tasks_ai/pipeline_hooks.py:214) refuses PROGRESSING until the
  blocker is ARCHIVED.
- Commit e7be8c52 "Pipeline suites record research before PROGRESSING; check.py stops
  ignoring the pipeline suites" on branch 396-task-pipeline-suites-are-vacuous-be already
  contains the fix for the ~30 research-gate failures. 396 is P1 and still PROGRESSING,
  i.e. not merged; duplicating its change here will conflict with it on merge.