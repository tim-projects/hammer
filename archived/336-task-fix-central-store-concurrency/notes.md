
- Progress:
Landing notes (all verified against the full suite: 4 pre-existing
test_robustness failures, identical on main, tracked by task 326):

1. store_lock lives in tasks_ai/utils.py, NOT a new module. Clone-based
   fixtures (HammerTestBase + per-feature copy lists) check out main and copy
   a file list that includes tasks_ai/utils.py; any new module imported by a
   copied file breaks every such fixture. Keep shared code in utils.py.

2. 'tasks undo' was never dispatched: tasks.py parsed the undo subparser but
   had no elif branch, so it consumed the args and exited 0 with no output
   (the "silently no-ops" note in tests/test_store_writes.py was this, not a
   fixture quirk). Fixed in tasks.py.

3. Fast-track gate: a fast-forward merge (what 'repo merge' runs) erases all
   git-level evidence that a branch did work - both merged-with-work and
   zero-commit branches are plain ancestors of main, and merge-base / git
   cherry both see nothing post-merge. The gate now also requires the synced
   commit list in the task record (parts['commits'], written at checkpoint),
   the only surviving evidence.

4. Locked transactions: counter allocation (tasks_ai/counter.py), worktree
   manifest mutations (create/remove/prune in tasks_ai/worktree_manager.py),
   and undo now run under one flock. commit_task_paths takes the lock
   re-entrantly, so every store mutation (checkpoint/move/modify/link/audit)
   funnels through it with no deadlock.

5. New gaps found while testing, worth their own tasks:
   - --dev mode swaps the store but NOT the git repo, so a dev-mode create
     writes branches into the real repo (my repro created a stray branch).
   - git init here defaults to 'master'; fixtures must create 'main'
     explicitly.
   - tests/tasks_ai is stale package junk shadowing the real package once
     pytest puts tests/ first on sys.path.