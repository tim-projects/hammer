RESEARCH (481 - worktree-local promotion):
- Verified: promote_task (git_service.py:560) pipeline_map at ~:602 maps TESTING->'testing', STAGING->'staging' (shared refs); merge_branches (:385) then checks out those refs in the main repo root - the concurrency defect.
- promote_task already resolves the worktree path (wt_path) for the auto-commit block at :579-594 - reuse that for cwd on stage merges.
- IMPORTANT: repo.py:292 cmd_merge_task_worktree already merges into a registered task branch inside its worktree (landed by 447/451) - align with or reuse it rather than inventing a second worktree-merge path.
- Lazy tasks (455) may have no branch yet (Br empty) - promote must handle the no-branch case (create on demand) instead of skipping.
- Proof method: git for-each-ref diff before/after each dev move must show only refs owned by that task.
