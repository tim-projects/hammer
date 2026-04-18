# Task 91: Modularize CLI commands

## Progress
- Extracted `config`, `doctor`, and validation logic into separate files: `tasks_ai/commands.py` and `tasks_ai/validation.py`.
- Fixed multiple lint/syntax errors across the project.
- Implemented full `doctor` logic.
- Updated `tasks_ai/cli.py` to store absolute tool paths in `.tasks/config.yaml`.
- Updated `check.py` to support absolute tool paths by matching the tool basename against available commands.

## Findings
- Test failure was caused by two issues:
  1. Incorrect configuration key structure in `tests/test_tasks.py` (nested vs. flat).
  2. `check.py` failing to recognize absolute tool paths saved in `config.yaml`.

## Mitigations
- Updated `tests/test_tasks.py` to use flat configuration keys.
- Modified `check.py` to resolve absolute tool paths to their basenames for command lookup.
- Verified configuration saving uses absolute paths via `tasks_ai/cli.py` update.
