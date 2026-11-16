1. 1. Add a regression test reproducing a merge into a task branch already checked out in its registered worktree.
2. 2. Update the generic `repo merge` fallback to resolve task-branch destinations through the worktree manifest and run the merge in that worktree.
3. 3. Preserve task-to-pipeline routing and safe handling of dirty worktrees.
4. 4. Run the focused regression tests and `./hammer check all`.