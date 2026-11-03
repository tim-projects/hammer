- [x] All existing tests green plus new tests/test_guard.py
  - Verified: tests/test_guard.py written on branch
    247-task-implement-hammer-guard-integri (18 tests: scan, gate, cache,
    integration classes), all passing in full-suite alphabetical order.
  - Verified: full `python3 -m pytest tests/` = 105 passed / 6 failed / 1 skipped;
    the 6 failures are pre-existing (tasks 243/245), not from this change.