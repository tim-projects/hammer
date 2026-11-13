1. Reproduce both failure classes and identify which tests fail standalone vs only in-suite
2. Confirm cli.py:158's env-only store isolation keeps repo_root on the fixture repo (no repo swap)
3. Change HammerTestBase.run_tasks to env-only isolation; update tests that genuinely need --dev to pass it explicitly
4. Leak-proof the base fixture: try/finally for HAMMER_DEV_TASKS_DIR and cwd
5. Fix remaining fallout test by test; run the full suite until only task 326's failures remain
6. Run ./hammer check all
7. Suite regression: harness runs every command with --dev, which now swaps the repo