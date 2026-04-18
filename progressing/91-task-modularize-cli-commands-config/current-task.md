# Task 91: Modularize CLI commands

## Progress
- Extracted `config`, `doctor`, and validation logic into separate files: `tasks_ai/commands.py` and `tasks_ai/validation.py`.
- Fixed multiple lint/syntax errors across the project (`check.py`, `repo.py`, `tests/test_tasks.py`).
- Added `PYTHONPATH` configuration to `check.py` to resolve `ModuleNotFoundError` during tests.

## Findings
- `pytest` was failing due to `tasks_ai` not being in `PYTHONPATH`.
- Several files had `E702` (multiple statements on one line) and syntax errors that needed manual fixing.
- The `doctor` method needs a full implementation in `tasks_ai/commands.py`, currently stubbed.

## Mitigations
- Manually fixed syntax and linting errors to satisfy `check.py all`.
- Updated `check.py` to dynamically set `PYTHONPATH` for sub-processes.

## Progress Update
- Resolved  by dynamically setting  in  for test runs.
- Implemented  logic in  with the extracted code.
- Verified that linting passes and most tests pass; investigating remaining test failure.

## Progress Update
- Resolved `ModuleNotFoundError` by dynamically setting `PYTHONPATH` in `check.py` for test runs.
- Implemented `doctor` logic in `tasks_ai/commands.py` with the extracted code.
- Verified that linting passes and most tests pass; investigating remaining test failure.
