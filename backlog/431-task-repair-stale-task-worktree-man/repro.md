1. 1. Register a task worktree in `.tasks/worktrees.json`.
2. 2. Delete the registered worktree directory while leaving the branch intact.
3. 3. Run `hammer tasks doctor --fix <task-id>`.
4. 4. Run `hammer tasks move <task-id> ARCHIVED -y`.
5. 5. Before the fix, Doctor leaves the stale manifest entry and archive is rejected by `GUARD_WORKTREE_MISSING_WORKTREE`.