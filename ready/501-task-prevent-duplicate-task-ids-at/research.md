RESEARCH (501 - duplicate-id prevention):
- Verified: no existing-ref check found in the create path (create.py / task_service.py have no 'already exists' guard); after 455, tasks are created lazily and branches/worktrees are created later (worktree_manager.py:94 create_task_worktree is the main ref-creation point) - the uniqueness check must live at ref CREATION (create_task_worktree / branch creation), not only at 'tasks create'.
- Gate-time protection exists (GuardGateHook, pipeline_hooks.py:34-66; the 315 incident proved it works) - keep it as defense in depth.
- The old failure mode: two branches claiming one id had to be cleaned by hand (hammer-issues-1.md section 5). New behavior: refuse naming the existing ref.
- Test: replay the incident (two <id>-* refs) end to end.
