Baseline measured at the moment the 402 fix landed (./hammer check all on the real repo, exit 1):

1. lint = ruff check . -> 27 errors. Kinds and spots: F841 unused variable (tasks_ai/audit.py:85 task_rel, plus three in tests), RUF034 (tasks_ai/audit.py), BLE001 x3, E722, S110 x2, S112 x2, PLW1510 subprocess.run without check x5, RUF100 unused noqa x4, F821 undefined name (tasks_ai/commands/audit.py:16 task_folder_name - the same line pyright reports), SIM115 x3, F401, I001.

2. test = pytest -> exit 2. The pipeline gate drives Validator.run_all, which runs a bare `pytest` in the project root (no test-file list, no PYTHONPATH - unlike check.py, which pins an explicit list). The run aborts in collection: root-level scratch file test_is_merged.py raises FileNotFoundError on a MagicMock main_repo_root, so pytest never runs a single test. Task 404/405 track the individual suite failures; the collection abort itself is untracked.

3. typecheck = pyright -> 1 error: tasks_ai/commands/audit.py:16:56 reportUnboundVariable task_folder_name (the same line as the F821 above).

4. format = ruff format . --check -> about 80 unformatted files, including check.py, check_cols.py, check_env.py, check_shutil.py, check_width.py, dev_feature.py, repo.py, setup_test_env.py, tasks.py, the whole tasks_ai/ package, and the root scratch test_*.py files. No existing task tracks format debt.

The ruff count is a moving target (16 earlier in the session, 21 at task creation, 27 now) because other agents land merges into main continuously. Re-measure before and after each fix; never hard-code a count as pass/fail. Task 243 already owns the ruff debt with a stale count of 11 and must be refreshed with the re-measured number rather than opening a second ruff task.
