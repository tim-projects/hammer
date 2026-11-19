1. ```
2. cd ~/git/tasks-ai
3. # 1. standalone: passes
4. python3 -m pytest tests/test_dev_isolation.py::TestDevInitOnAFreshStore::test_store_records_without_a_git_repo_are_refused_not_clobbered -q
5. # 2. in-file context on unmodified main: 1 failed, 9 passed
6. python3 -m pytest tests/test_dev_isolation.py -q
7. # 3. store race: passes standalone, fails in some full-suite runs
8. python3 -m pytest tests/test_store_writes.py::TestStoreCommitsAreScopedPerCommand::test_concurrent_unlink_and_checkpoint_stay_scoped -q
9. python3 -m pytest tests/ -q 2>&1 | tail -3
10. ```