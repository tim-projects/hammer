---
Task: 497-task-gate-pr-exit-with-merge-viabil
---

- Progress: Implemented PR-entry freshness merge, merge-tree conflict detection, validation freshness, provisioning-relative patch refresh, and explicit per-patch MD5 approval. Added focused regression tests for conflict paths, stale validation, edited-patch invalidation, approval refusal, and force refusal. Focused suite passes: 24 tests plus 11 subtests; ./hammer check all passes.
- Findings: PR exit must validate before provisioning receives a merge. The numeric repo-merge fixture initially exposed an approval/path mismatch: approval patches belong under .tasks/review/<numeric-id>/patches, while ordinary review tooling uses .tasks/review/<task-folder>/patches. The shared approval helper now owns the numeric-ID contract, and review artifact-only folders are excluded from guard duplicate-state detection.
- Mitigations: All implementation remains in .task-worktrees/497-task-gate-pr-exit-with-merge-viabil. Approval is checked before patch regeneration so edited patches cannot be silently overwritten; --force cannot create or bypass approval. Main checkout remains clean. Next: commit the task branch, move 497 through TESTING, REVIEW, STAGING, PROVISIONING, and DONE using hammer transitions.
