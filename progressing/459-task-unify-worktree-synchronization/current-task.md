---
Task: 459-task-unify-worktree-synchronization
---

## Implementation

- Made `WorktreeSyncHook` the canonical branch/worktree synchronization path.
- Removed `tasks_ai/commands/mount.py:_sync_or_warn`; `tasks mount` now delegates to the hook.
- Missing task branches/worktrees are created from local main.
- Local main is the merge source; `origin/main` is fetched only to detect divergence.
- Added non-mutating conflict and uncommitted-file checks with actionable `action_required` blockers.
- Added blocker messages containing task ID, branch, local main commit, paths, and resolution steps.
- Replaced duplicate mount tests with shared-hook and mount/pipeline parity regressions.

## Verification

- `python3 -m pytest -q`: 350 passed, 1 skipped, 290 subtests passed.
- `./hammer check all`: lint, test, typecheck, and format all passed.
