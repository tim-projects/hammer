1. Reproduce both failure classes; separate standalone failures from cascade failures
2. Enumerate the dev write surface (store, throwaway repo, guard cache, hooks dir, backups, install/upgrade) and block each path outside the two dev roots: remove the parent-remote fallback in dev, refuse 'tasks upgrade' in dev
3. Narrow the dev push refusal to parent-repo-remote targets only (keep refusing those); add a test that a mock-remote push from dev still works and a real-remote push is still refused
4. Make repo-swap-aware harness tests resolve the CLI's repo as <store>-repo or read paths from tool JSON output
5. Leak-proof the base fixture: try/finally for HAMMER_DEV_TASKS_DIR and cwd
6. Add the dev-write audit test (path allowlist under the two dev roots) as the invariant's regression guard
7. Fix fallout test by test; full suite until only task 326's failures remain
8. Run ./hammer check all