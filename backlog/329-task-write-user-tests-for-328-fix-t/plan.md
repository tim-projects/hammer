1. Grep for any existing store-mutation helper or lock pattern before writing new code (there is currently no locking anywhere in tasks_ai/)
2. Replace add --all at commands/checkpoint.py:16 with a task-scoped pathspec (git add <state>/<folder>)
3. Make add/commit failures fatal in checkpoint: check returncode and cli.error on failure
4. Fix sync_task_content: diff against cli.tasks_path (or read part files directly from the task dir) instead of the main repo; pass explicit cwd to every git call
5. Add tests: parallel-checkpoint bleed, induced git failure, sync-from-worktree-cwd
6. Run ./hammer check all; move task through pipeline