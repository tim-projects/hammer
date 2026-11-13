1. Decide isolation floor: refuse repo-touching commands in dev mode (option 1) vs throwaway repo (option 2)
2. If option 1: enumerate every entry point that reaches main_repo_root (worktree manager, counter, guard, is_merged, fetch) and gate each behind the dev check
3. If option 2: bind main_repo_root to a temp clone keyed on HAMMER_DEV_TASKS_DIR, created on first use, cleaned on teardown
4. Add tests: repo-bytes-unchanged after dev cycle; real promotion unaffected by dev-created ids
5. Run ./hammer check all; document the chosen model in AGENTS.md
6. Dev mode creates real branches and worktrees in the main repo