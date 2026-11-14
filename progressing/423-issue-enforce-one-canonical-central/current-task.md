---
Task: 423-issue-enforce-one-canonical-central
---

- Progress: Implemented canonical production store resolution, independent store Git-top-level checks, guarded every direct store write, read-only local-store detection, and branch materialization refusal. Added tests/test_central_store.py. Focused lifecycle tests pass; lint, typecheck, and format pass.
- Findings: Root cause: git rev-parse --is-inside-work-tree treated a plain .tasks directory inside the code repo as an independent store; direct store adds/commits then advanced the code default branch and invalidated PatchSnapshot.
- Mitigations: The unrelated no-default-branch snapshot crash is tracked in task 425 and must be merged before task 423 can pass the unchanged validation gate.
