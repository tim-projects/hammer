1. ./hammer tasks --dev init
2. Create two tasks and move both to PROGRESSING (tasks --dev create ...; tasks --dev move <id> PROGRESSING)
3. From a worktree on one task's branch, run ./hammer tasks --dev checkpoint with NO task id
4. Observe: the tool silently picks an arbitrary PROGRESSING task, sync_task_content writes that task's record (commits/notes) and commits it in .tasks; the agent intended the other task, so the record now carries another task's branch commits (data corruption by mislabeling)
5. Repeat with ./hammer tasks --dev current (no id): reports the arbitrary task as active