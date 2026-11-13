As a Hammer user, when I run `tasks mount <id>` to open a task worktree, I want
hammer to bring that worktree up to date with the default branch before I start
typing: if the worktree has no work of its own it should be synced to main, and
if it has work hammer should tell me which files would conflict with main so I
can resolve them before they surface at promotion time.
