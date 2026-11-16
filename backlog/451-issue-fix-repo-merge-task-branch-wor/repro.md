1. 1. Create or mount a task worktree so its task branch is checked out under `.task-worktrees/`.
2. 2. From the main worktree, run `./hammer repo merge -y main <task-branch>`.
3. 3. The command attempts `git checkout <task-branch>` in the main worktree and fails with `fatal: '<task-branch>' is already used by worktree at ...`.