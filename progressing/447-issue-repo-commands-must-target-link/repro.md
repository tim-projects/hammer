1. 1. Create a linked task worktree and make a source change inside it.
2. 2. Leave an untracked .tasks-repo directory in the main repository.
3. 3. Run hammer repo commit from the task worktree.
4. 4. Observe that the command resolves the main repository, stages .tasks-repo as a gitlink, and commits on main.