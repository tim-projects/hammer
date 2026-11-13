1. 1. Create a task and move it to PROGRESSING (creates and syncs its worktree).
2. 2. In that worktree commit a change to file X.
3. 3. On the default branch commit a conflicting change to file X.
4. 4. Run `cd <main repo> && ./hammer tasks mount <task id>`.
5. 5. Observed: mount prints only the worktree path. No warning about X, no sync.
6.    The conflict is only discovered later at `tasks move <id> TESTING`.
7. 
8. Expected after fix:
9. 4'. Mount prints a warning naming X as conflicting with the default branch
10.     (worktree untouched), or, when the worktree has no work of its own, syncs
11.     it to the default branch and prints that.