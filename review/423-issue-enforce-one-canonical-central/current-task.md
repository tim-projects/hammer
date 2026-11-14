---
Task: 423-issue-enforce-one-canonical-central
---

- Progress: Implementation and regressions complete. Also fixed the no-default-branch PatchSnapshot blocker tracked by task 425 so the unchanged validation gate can pass; the focused default-branch, central-store, audit, and worktree tests are green.
- Findings: Root cause: git rev-parse --is-inside-work-tree treated a plain .tasks directory inside the code repo as an independent store; direct store adds/commits then advanced the code default branch and invalidated PatchSnapshot.
- Mitigations: Task 425 remains as the tracking record for the pre-existing no-default-branch defect; its fix is included in task 423 to unblock the mandatory validation gate.
