---
Task: 467-task-add-optional-unref-lint-checks
---

- Progress: Implemented repo.lint_secondary=unref as an explicit opt-in companion to Ruff in both Validator and legacy check.py. Unref runs in the task worktree even when Ruff fails, reports separate secondary output, fails actionably when missing, and receives no autofix flag. Added config key, README/TROUBLESHOOTING docs, and 7 focused regression tests. Verification: focused tests 7 passed; adjacent suites 21 passed; ruff check . passed; ./hammer check all passed lint/test/typecheck/format.
- Findings: 
- Mitigations: 
