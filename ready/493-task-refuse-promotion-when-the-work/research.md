RESEARCH (493 - dirty-worktree refusal):
- Verified: promote_task auto-commits any dirty worktree state at git_service.py:579-594 ('Auto-commit before transition') - the silent-WIP merge hazard.
- Existing discipline to mirror: cmd_merge_task_worktree (repo.py:292+) refuses when the registered worktree is dirty or on the wrong branch, with a 'tasks mount' remedy hint.
- New behavior: refusal lists the offending paths and names ./hammer repo commit -m as the remedy; zero commits created (assert git log unchanged in tests).
- Also update any docs/help text claiming commits happen automatically (AGENTS.md + command help).
