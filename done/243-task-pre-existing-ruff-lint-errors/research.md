Research pass on task 243 (ruff lint debt), repository /home/vscode/git/tasks-ai.

Re-measured on main (c6d960a4) with `python3 -m ruff check . --output-format=concise`:
54 errors total, of which 27 belong to the project and 27 are byte-identical duplicates
under `.tasks-repo/` (a tracked git 160000 link to a full nested clone of this repo,
added by commit c6d960a4; nothing in the source tree references that path, so it is
accidental pollution rather than a second copy of the debt to fix).

The 27 in the project, by file:
- tasks_ai/audit.py (5): F841 task_rel L85, RUF034 L88, BLE001 L103, E722 L138, S110 L138
- tasks_ai/check_wrapper.py (2): RUF100 unused noqa E402 L27 and L28 (that code is not
  enabled by this config, the directives are dead)
- tasks_ai/commands/audit.py (2): F821 task_folder_name L16 (same line pyright reports,
  used before its assignment on L17), BLE001 L41
- tasks_ai/commands/create.py (3): S112 L116, BLE001 L178, S112 L219
- tasks_ai/commands/doctor.py (1): S110 L290
- tests/test_audit_verify_integration.py (7): PLW1510 L62/L214/L328/L348, RUF100 L64/L216,
  SIM115 L358
- tests/test_default_branch.py (3): RUF100 L18, F841 L187, F841 L216
- tests/test_help_coverage.py (1): F401 sys L20
- tests/test_tasks.py (3): I001 L2, SIM115 L487, SIM115 L488
14 of the 27 are auto-fixable with --fix; the rest need a real edit. Root-level scratch
files test_*.py are already clean (checked directly).

Where the previous count of 11 came from: it predates tasks 358/386/396 landing on main
(check_wrapper.py, tests/). The count is a moving target; re-measure at review time.