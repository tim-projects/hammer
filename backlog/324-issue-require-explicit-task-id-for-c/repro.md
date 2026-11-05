1. 1. ./hammer tasks --dev init
2. 2. Create two tasks (e.g. tasks --dev create 'First task for repro aaa' and 'Second task for repro bbb') and move both to PROGRESSING
3. 3. From a worktree on one task's branch, run ./hammer tasks --dev checkpoint with NO task id
4. 4. Observe: the tool silently picks an arbitrary PROGRESSING task, sync_task_content writes that task's record (commits/notes) and commits it in .tasks — the agent intended the other task, so the record now carries another task's branch commits (data corruption by mislabeling)
5. 5. Repeat with ./hammer tasks --dev current (no id): reports the arbitrary task as 'active'