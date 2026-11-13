1. 1. Re-measure ./hammer check all on main and record the four numbers as they stand that day
2. 2. Make pytest collectible first: remove or move the root scratch test_*.py files (task 368 owns scratch cleanup)
3. 3. Fix the ruff errors suite by suite, refreshing task 243 rather than opening a second ruff task
4. 4. Fix the single pyright error in tasks_ai/commands/audit.py
5. 5. Run ruff format across the repo, then re-run ./hammer check all until it exits 0