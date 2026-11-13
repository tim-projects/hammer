1. Commit or stash the 5 currently modified files so the cleanup commit stays reviewable
2. git rm the 31 root scratch files and 8 artifacts in one commit
3. git rm -r tests/tasks_ai plus the 5 stale tests files in a second commit
4. Delete the untracked transient files listed in criterion 8; never touch .tasks, .tasks.backup, .task-worktrees, venv
5. Run ./hammer check all, then review the REVIEW diff for regressions before promotion