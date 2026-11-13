1. 1. In merge_branches (tasks_ai/git_service.py:353-356), on merge failure run
2.    `merge --abort` and raise PipelineMergeConflict(src, target) instead of
3.    RuntimeError.
4. 2. Keep the existing move.py:160-164 handler as the single user-facing gate:
5.    MERGE_CONFLICT with hint data/hints.json:34.
6. 3. Decision needed on `--force` (move.py:157): keep the bypass but log a
7.    warning that merges are skipped, or route forced moves through the check.
8. 4. Add a regression test that reproduces a conflicting promotion and asserts
9.    the error code plus no in-progress merge afterwards.
10. 5. Run ./hammer check all and resolve any pre-existing failures per AGENTS.md.