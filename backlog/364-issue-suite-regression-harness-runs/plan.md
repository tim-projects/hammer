1. Reproduce both failure classes; separate standalone failures from cascade failures
2. Narrow the dev push refusal to parent-repo-remote targets only (keep refusing those); add a test that a mock-remote push from dev still works and a real-remote push is still refused
3. Make repo-swap-aware harness tests resolve the CLI's repo as <store>-repo or read paths from tool JSON output
4. Leak-proof the base fixture: try/finally for HAMMER_DEV_TASKS_DIR and cwd
5. Fix fallout test by test; full suite until only task 326's failures remain
6. Run ./hammer check all
7. Suite regression: harness runs every command with --dev, which now swaps the repo