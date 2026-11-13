Research pass on task 406 (repository: /home/vscode/git/tasks-ai, branch 406-task-fix-the-check-all-baseline-deb, HEAD c6d960a4 == origin/main + local auto-commit).

Measured baseline, 2026-11-10, `./hammer check all` on main:

1. lint = ruff check . -> 54 errors, not 27. Exactly 27 in the repo itself
   (tasks_ai/audit.py 5, tasks_ai/check_wrapper.py 2, tasks_ai/commands/audit.py 2,
   tasks_ai/commands/create.py 3, tasks_ai/commands/doctor.py 1,
   tests/test_audit_verify_integration.py 7, tests/test_default_branch.py 3,
   tests/test_help_coverage.py 1, tests/test_tasks.py 3). The other 27 are byte-identical
   duplicates under `.tasks-repo/` -- that path is a full nested clone of this repo
   (tracked as a git 160000 link, added by commit c6d960a4 "[396] Auto-commit before
   TESTING transition", pointing at 6236287a). `git ls-files -s .tasks-repo` confirms the
   link; nothing in tasks_ai/, check.py, tasks.py, repo.py, scripts/ references the path
   (grep is empty), so it is accidental pollution, not a fixture. Treat it as tooling
   noise, not as second ruff debt: see the task ticket for the decision taken.

2. test = pytest -> bare `pytest` in the project root aborts during collection with
   FileNotFoundError on the root-level scratch file test_is_merged.py (line 8 calls
   tasks_ai/git_service.is_merged against a MagicMock cwd). The root scratch files are
   tracked: test_create_logic.py, test_is_merged.py, test_pairing_logic.py, test_regex.py.
   Constraining the run to the real suite (`pytest tests/ -q`) gives 252 collected,
   39 failed / 212 passed / 1 skipped / 270 subtests passed in 909s. Root causes:
   - ~30 of the 39 are the READY -> PROGRESSING research gate (tasks_ai/pipeline_hooks.py
     ResearchGateHook, registered in tasks_ai/cli.py:63, landed on main via 45c3a128):
     tests create a task and move it straight to PROGRESSING without recording research,
     so the move fails and every later assertion in the suite fails with it.
   - tests/test_require_task_id.py:93 and tests/test_robustness.py:383 fail with
     FileNotFoundError on a criteria.md/path under .tasks/testing/<task>; a
     `TypeError: expected str, bytes or os.PathLike object, not NoneType` from
     subprocess.run appears in test_store_concurrency.py.
   NOTE: task 396 (branch 396-task-pipeline-suites-are-vacuous-be, commit e7be8c52
   "Pipeline suites record research before PROGRESSING; check.py stops ignoring the
   pipeline suites") already contains the fix for most of these and is not merged yet.

3. typecheck = pyright (npx pyright) -> exactly 1 error:
   tasks_ai/commands/audit.py:16:56 reportUnboundVariable task_folder_name. Line 16 uses
   the variable, line 17 assigns it (os.path.basename(current_path)); a plain ordering
   bug, the declared fix is to move the assignment above its first use.

4. format = ruff format . --check -> 136 files would be reformatted (112 already clean),
   including check.py, repo.py, tasks.py, the whole tasks_ai/ package, tests/, and the
   root scratch test_*.py files.

5. The Validator drives pytest as a bare `pytest` in project_root with a 300s timeout
   (tasks_ai/validator.py run_check, and check.py run_check). The full suite needs 909s,
   so even with every failure fixed the gate times out before the fix is visible.
