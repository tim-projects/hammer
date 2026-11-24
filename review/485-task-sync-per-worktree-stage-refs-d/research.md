RESEARCH (485 - demote down-sync):
- Verified: demote_task (git_service.py:665) still merges the shared staging/testing branches back into the worktree branch - refs that will no longer receive stage merges after 481 lands.
- It already resolves wt_path and falls back to repo_root - keep the fallback, change the branch list to the per-worktree chain: origin/main-><id>-PR-><id>-STAGING-><id>-TESTING->Br (full when demoting toward PROGRESSING, truncated chains otherwise).
- Merge conflicts must abort with paths (no auto-resolve) - mirror cmd_merge_task_worktree's status/check discipline (repo.py:292+).
- Downstream: gates task 487 checks these refs after demote+re-promote; keep the two consistent.
