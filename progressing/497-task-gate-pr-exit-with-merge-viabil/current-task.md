---
Task: 497-task-gate-pr-exit-with-merge-viabil
---

- Progress: Implemented PR-entry freshness merge, merge-tree conflict detection, validation freshness, provisioning-relative patch refresh, and explicit per-patch MD5 approval. Added focused regression tests for PR-entry freshness, conflict paths, stale validation, exact provisioning-relative patch bytes, edited-patch invalidation, approval refusal, and --force refusal. Focused suite passes: 26 tests plus 11 subtests; ./hammer check all passes.
- Findings: Review found that the initial focused tests did not directly prove PR-entry freshness, exact patch bytes, or --force refusal. Added direct coverage for all three. The approval path contract is .tasks/review/<numeric-id>/patches; ordinary review tooling remains .tasks/review/<task-folder>/patches, and review artifact-only folders are excluded from guard duplicate-state detection.
- Mitigations: All implementation and test changes remain isolated in .task-worktrees/497-task-gate-pr-exit-with-merge-viabil. Approval is checked before patch regeneration so edited patches cannot be silently overwritten; --force cannot create or bypass approval. Main checkout remains clean. Next: re-run the task through TESTING and REVIEW, then complete regression review and promote through STAGING, PR, PROVISIONING, and DONE.
