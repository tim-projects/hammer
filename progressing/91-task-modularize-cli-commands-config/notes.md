# Task 91: Modularize CLI commands

## Progress
- Extracted `config`, `doctor`, and validation logic into `tasks_ai/commands.py` and `tasks_ai/validation.py`.
- Updated `tasks_ai/cli.py` to save absolute tool paths in `.tasks/config.yaml`.
- Updated `check.py` to support absolute paths and robust configuration key lookups.

## Findings
- Test failures persist in `test_review_diff_generated`.
- Configuration loading in `check.py` is failing in the test environment, causing `tool` to be `None` (no tool configured).
- Despite tests writing a flat `config.yaml`, `check.py` appears unable to retrieve keys reliably within the test execution sandbox.

## Mitigations
- Investigating `check.py` configuration loading specifically within the test sandbox.
- Verified test configuration uses correct flat keys.
- Continuing to trace tool path configuration in the modularized architecture.
