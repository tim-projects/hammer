- [x] All existing tests green plus new tests/test_guard.py
  - Verified: full `python3 -m pytest tests/` = 105 passed / 6 failed / 1 skipped.
    The 6 failures are the pre-change baseline (4 in test_robustness, 2 in
    test_worktree_system; tracked by tasks 243/245). Zero new failures.
  - Verified: tests/test_guard.py added, 18 tests, all passing.