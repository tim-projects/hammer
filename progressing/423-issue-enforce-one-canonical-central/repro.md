1. 1. Run pytest -q tests/test_default_branch.py::TestMasterNamedRepo::test_promotion_resolves_master on main and observe AUDIT_MISMATCH
2. 2. Inspect the temporary repository history and observe Audit, Review, and Review summary commits advancing master
3. 3. Run pytest -q tests/test_worktree_system.py::TestWorktreeSystem::test_worktree_removed_on_archived and observe the same snapshot mismatch
4. 4. Configure or encounter a .tasks directory inside a task worktree and observe that the current-worktree guard does not detect local stores from the main repository