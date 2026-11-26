---
Task: 497-task-gate-pr-exit-with-merge-viabil
---

- Progress: Implemented PR-entry freshness, merge-tree conflict detection, validation freshness, provisioning-relative patches, and explicit MD5-bound approval. PR exit then exposed a shared-branch ownership bug: provisioning was checked out in task 489's worktree, so merging from the main checkout failed with PipelineBranchMissing. Fixed the merge to run in the worktree that owns provisioning and added a direct regression test. Focused suite passes: 11 tests plus 3 subtests; ./hammer check all passes.
- Findings: The provisioning ref existed, but Git correctly refused to check it out in the main checkout because task 489's registered worktree already owned that branch. The prior implementation assumed the main checkout always owned provisioning. Review coverage now directly exercises PR freshness, exact patch bytes, force refusal, conflict paths, and provisioning branch ownership.
- Mitigations: The provisioning merge now resolves the branch's current worktree owner before checkout and falls back to the main checkout only when no worktree owns it. Approval remains explicit, MD5-bound, checked before patch regeneration, and cannot be bypassed with --force. All changes remain isolated in task 497's worktree; next, commit, re-promote through TESTING/REVIEW/STAGING/PR, refresh approval, and complete PROVISIONING/DONE.
