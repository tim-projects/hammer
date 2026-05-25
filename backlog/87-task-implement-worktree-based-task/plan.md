1. Worktree Registry: Implement `WorktreeManager` to maintain a manifest (`.tasks/worktrees.json`) mapping `TaskID` to `WorktreePath`.
2. Mount Command: Introduce `tasks mount <id>` to create worktrees via `git worktree add`.
3. Context-Awareness: Update `TasksCLI` to detect worktree context and resolve paths relative to the specific task's worktree location.
4. Gated Integration: Ensure the pipeline gates (Task 178) function correctly when executed from within a task worktree.
5. Cleanup: Integrate automatic `git worktree remove` into the `ARCHIVED`/`DONE` transition logic within `TasksCLI._move_logic`.
6. Backward Compatibility: Ensure the existing branch-switching workflow (`repo checkout`) remains functional for simpler tasks.
7. Documentation & Testing: Provide conflict resolution tools, update documentation, and perform multi-task testing.
