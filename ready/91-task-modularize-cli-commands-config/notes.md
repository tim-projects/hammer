# Task 91: Modularize CLI commands

## Progress
- Extracted `config`, `doctor`, and validation logic into separate files.
- Updated `tasks_ai/cli.py` to store absolute tool paths.
- Updated `check.py` to support absolute tool paths by matching basename.
- Updated `_run_validation` in `tasks_ai/cli.py` to correctly resolve the project root using the task path when available.

## Findings
- Test failures were caused by `check.py` running in the main project root instead of the task-specific sandbox during tests, leading it to load the wrong configuration.

## Mitigations
- Modified `_run_validation` to determine the project root based on the task path, ensuring it picks up the correct `.tasks/config.yaml` within the test environment.
