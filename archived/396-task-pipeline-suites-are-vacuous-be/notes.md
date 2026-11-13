# 396 progress

## Root causes fixed (all in tests, one in check.py)
1. Research-gate vacuity: helpers moved READY -> PROGRESSING unchecked, so tasks stuck in READY and downstream gate assertions were vacuous. Fixed with `enter_progressing` helpers (tests/test_tasks.py, tests/test_robustness.py), a `--research` record in tests/test_all_transitions.py, and READY/PROGRESSING loops in tests/test_store_writes.py.
2. `complete_criteria` walked the store and marked the first criteria.md found: the auto-created "Write user tests for <id>" pair in BACKLOG (backlog sorts before progressing). The pair's unchecked copy resurfaced as UNFINISHED_CHECKBOXES at the STAGING gate. Fixed: the helper marks THIS task's criteria and accepts a file name or numeric id.
3. Fixture store-repo root cause: `.tasks` had no git repo in the robustness fixture, so `commit_task_paths` (cwd=cli.tasks_path) fell through to the outer repo. The choreography's `git checkout main` then rewrote .tasks, reverting the task to an older stage with unchecked criteria. Fixed with `git init` on `.tasks` in setUp, matching production.
4. check.py hardcoded `--ignore` for nine pipeline suites behind a "known-failing" comment, keeping check all green while they were red. All nine pass now; ignores removed, files listed explicitly.

## Boundary (not fixed here, linked)
- Task 402: `tasks init` seeds .tasks/config.yaml with every tool set to /bin/true, so `check all` runs nothing. Own task.
- Task 404 (created here, baseline captured): 11 pre-existing failures in suites outside check.py's explicit list (test_default_branch 3, test_dev_write_audit 2, test_guard 1, test_require_task_id 2, test_store_concurrency 2, test_worktree_system 1). 404 linked to 402.
- Full root pytest collection also errors at collection on the tracked root file test_is_merged.py (MagicMock main_repo_root) - noted in 404's baseline via 402.

## Verification
- tests/test_tasks.py 10 passed; tests/test_robustness.py 48 passed; tests/test_all_transitions.py pass; tests/test_store_writes.py 18 passed.
- The exact check.py pytest invocation (explicit list, PYTHONPATH=root, root collection) ran green for every listed suite; failures observed were confined to files not in the list and are task 404's baseline.
- ruff lint + format clean on the branch.
