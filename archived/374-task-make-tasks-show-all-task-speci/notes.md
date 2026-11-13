# 374 — tasks show --all is task-specific

## Fix (branch 374-task-make-...)
- tasks.py dispatch now forwards the filename: `show <id> --all` -> single-task all-data, bare `show --all` -> every task (366 behavior kept).
- tasks_ai/commands/show.py: `run_task_all(cli, filename)` resolves the task, derives its state from the store folder, and emits the same record as the all-tasks path (state/file/name/type/branch/metadata/files). `run()` routes on filename.
- Help text clarified.

## Verification
- Manual --dev: `show 354 --all` (text + -j record with 5 md files), `show --all` -> 252 tasks, `show 354` unchanged.
- tests/test_show_all.py extended: per-task JSON/text, bare --all still lists all, single unchanged. Fixture clones main, so green post-merge (same lifecycle as 366).
- ruff clean on all touched files.

## Debt
- Fixture harness tests main, not the task branch (pre-existing, tracked by 342/343).
