RESEARCH (483 - funnel lock + guard gate):
- Verified: merge_branches (git_service.py:385) has no serialization; repo.py contains no guard integration at all (the plan-guard phase-3 promotion gate never landed).
- Pattern to copy: store_lock in tasks_ai/utils.py:31-54 (flock, kernel-released on holder death, reentrancy via thread-local depth). Lock file at <main_repo_root>/.git/hammer-merge.lock - same filesystem for all worktrees, correct cross-process.
- Guard entry point: guard.py CLI 'check' subcommand (hammer guard check); hook variant GuardGateHook (pipeline_hooks.py:34-66) already REJECTs exit moves - the merge gate is the same verdict at merge time.
- HAMMER_INTERNAL_CALL env (git_service.py:41-45) is how hammer's own merges bypass the pre-merge-commit hook - keep setting it.
- Dev mode: lock acquisition must respect the dev repo root (context.repo_root), not the real one.
