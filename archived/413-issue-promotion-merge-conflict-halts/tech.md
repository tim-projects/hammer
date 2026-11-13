Two conflict paths exist today, one healthy and one broken:

1. Worktree sync on PROGRESSING (works): tasks_ai/pipeline_hooks.py:432-479
   (WorktreeSyncHook) merges origin/<default> into the task worktree. On conflict
   it runs `merge --abort` (pipeline_hooks.py:476) and halts with
   WORKTREE_MERGE_CONFLICT (pipeline_hooks.py:477).

2. Promotion merges (broken): tasks_ai/git_service.py:353-356 (merge_branches)
   raises a bare RuntimeError on conflict. Defects:
   - move.py:160-164 catches PipelineMergeConflict, which merge_branches never
     raises, so the MERGE_CONFLICT error code (data/errors.json:34) and hint
     (data/hints.json:34) are unreachable for promotions.
   - No `merge --abort` after the failed merge: the main repo is left mid-merge
     on the target branch (checkout happened at git_service.py:346). Every later
     command that touches that branch is stuck; a retry hits a second conflict.
   - RuntimeError is uncaught by tasks.py, so the user gets a Python traceback
     instead of a structured CLI error.
   - `--force` skips the merge entirely (move.py:157), so a forced promotion
     performs no conflict check at all.

No test covers either path (only a comment at tests/test_tasks.py:617).
