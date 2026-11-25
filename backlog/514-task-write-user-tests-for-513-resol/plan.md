1. 1. Add a `_merge_lock_dir(repo_root)` helper in `tasks_ai/utils.py` resolving `git rev-parse --git-common-dir` (relative output joined against `os.path.abspath(root)`; fallback `<root>/.git` when git fails), following `context.py:123-136` / `guard_engine.py:171-180`.
2. 2. Point `merge_lock`'s lock path at the resolved dir; drop the now-unneeded `os.makedirs`.
3. 3. Add the linked-worktree regression test to `tests/test_merge_lock_guard.py` (real `git worktree add`; assert lock-file location in the main common git dir and cross-root serialization).
4. 4. Verify: `python3 -m pytest tests/test_merge_lock_guard.py tests/test_repo_provisioning.py`, then `./hammer check all`.
5. 5. Merge 513 through the pipeline to main; task 489's worktree then syncs main before its funnel merge.