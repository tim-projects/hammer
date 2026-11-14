---
Task: 421-task-require-blockers-done-not-arch
---

- Progress: Reapplied task 421 manually onto current main after syncing the worktree. Preserved the newer JSON/blocker validation contract while adding Ruff --fix to check all. Focused tests: 6 passed; broader blocker/validation tests: 17 passed; full ./hammer check all passes.
- Findings: Current main had advanced the Ruff contract to --output-format=json and blocker-status reporting. The manual conflict resolution retained both newer behaviors and added --fix only for lint inside check all.
- Mitigations: No merge commit was created. Task branch HEAD equals current main and the task-only working-tree diff contains only the reapplied task changes.
