Add worktree creation/deletion commands to tasks.py via `tasks_ai/commands/` modules, leverage existing `ProjectContext` (tasks_ai/context.py:5) for worktree detection and `resolve_worktree_path()`, extend `GitService` (tasks_ai/git_service.py) for worktree-add/remove/prune operations, track worktree paths in task metadata (extend meta.json with WorktreePath field or a central `.tasks/worktrees.json` manifest), integrate worktree-to-main merges into `GitService.promote_task()` / `PipelineService.git_merge_transition()`, implement conflict detection via `GitService.run(["diff", ...])` and reporting, provide manual conflict resolution tools, integrate automatic `git worktree remove` into the `ARCHIVED`/`DONE` transition via `ArchivedCommitHook` (tasks_ai/pipeline_hooks.py:198) in `TasksCLI._move_logic` (which now delegates to `commands/move.py:move_logic`), and maintain backward compatibility with the existing branch-based workflow in `GitService.merge_branches()` / `BranchSyncHook`.

**Existing infrastructure to leverage:**
- `ProjectContext` (tasks_ai/context.py:5): `is_worktree`, `resolve_worktree_path()`, `resolve_path()`
- `GitService` (tasks_ai/git_service.py:7): `run()`, `get_current_branch()`, `get_default_branch()`, `branch_exists()`, `merge_branches()`, `promote_task()`, `demote_task()`, `push_tasks_branch()`
- `PipelineService` (tasks_ai/pipeline.py:14): `git_merge_transition()`, `validate_gate()`, `check_audit_integrity()`
- `move_logic()` (tasks_ai/commands/move.py:92): delegates to `PipelineService.git_merge_transition()` and runs hooks
- `ArchivedCommitHook` (tasks_ai/pipeline_hooks.py:198): handles git commit + auto-save on ARCHIVED
- `BranchSyncHook` (tasks_ai/pipeline_hooks.py:288): checks out branch and merges main into it on PROGRESSING
- `TaskService` (tasks_ai/task_service.py:7): `find_task()` for looking up tasks by ID/filename
- `FM` (tasks_ai/file_manager.py:21): `load()`/`dump()` for task file CRUD
- `Task` model (tasks_ai/models.py): metadata dict with Id, Ti, St, Cr, Bl, Pr, Br keys