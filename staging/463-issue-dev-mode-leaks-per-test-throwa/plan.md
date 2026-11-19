1. 1. `tasks_ai/context.py`: add `reclaim_stale_dev_dirs(tasks_path, now=None)` + call it on the cold
2.    path in `_ensure_dev_repo` (before cloning). Rules: tempdir only, `hammer_tasks_*` /
3.    `hammer_test_*` / `hammer_remote_*` prefixes (and their `-repo` clones), TTL 1 day, skip the
4.    current store and its repo.
5. 2. `tests/hammer_test_base.py`: replace the ignore_errors tearDown rmtree with `cleanup_dev_store`
6.    and register addCleanup for test_root/dev store/dev repo so setUp failures clean too.
7. 3. Tests (new `tests/test_dev_repo_reclamation.py`): stale swept / fresh kept / live kept;
8.    zero-net-growth name-diff for one base-based file; loud failure on rmtree error.
9. 4. Run affected files, then the full suite twice on a /tmp seeded with 500 stale dirs: identical
10.    results, dirs swept, no ENOSPC.