---
Task: 487-task-gate-stage-promotions-on-per-w
---

- Progress: - Implemented per-worktree stage-ref merge gates with actionable missing-ref errors and regression coverage.
- Focused tests: 4 passed, 4 subtests passed.
- Related pipeline suites: 50 passed, 7 subtests passed.
- Full ./hammer check all: lint, test, typecheck, and format passed.
- Findings: - Gate mapping: TESTING checks Br -> <id>-TESTING; STAGING checks <id>-TESTING -> <id>-STAGING; PR checks <id>-STAGING -> <id>-PR; PROVISIONING checks <id>-PR -> provisioning.
- Re-promotion after demotion accepts either ancestry direction; unrelated tampered refs fail.
- Mitigations: - Existing PR/PROVISIONING dev fixture now constructs the required local stage refs before promotion.
