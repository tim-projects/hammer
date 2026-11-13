Current mount path: tasks_ai/commands/mount.py run() calls
git.worktrees.create_task_worktree() and prints the `cd <path>` command. No
update, no conflict awareness: the worktree is whatever the last pipeline merge
left behind.

Existing machinery to reuse rather than rebuild:
- WorktreeSyncHook (tasks_ai/pipeline_hooks.py:432-479) already fetches
  origin/<default> with a local-branch fallback (pipeline_hooks.py:456-471),
  merges, and on conflict runs `merge --abort` + errors
  WORKTREE_MERGE_CONFLICT (pipeline_hooks.py:474-479). That flow moves into
  git_service so mount can call it.
- Conflict detection without touching the working tree:
  `git merge-tree --write-tree <default> <branch>` (git 2.47 confirmed here)
  writes no files and exits 1 when the merge would conflict, listing conflicted
  paths as stage lines `<mode> <oid> 1|2|3\t<path>`.
- "No work of its own" = no uncommitted or untracked changes
  (`git status --porcelain`) AND no commits ahead of the default branch
  (`git rev-list --count <default>..HEAD` = 0). A branch that satisfies both
  merges the default branch by fast-forward, so the auto-sync cannot conflict.

Merge must never be attempted on a worktree with local work: it would write
conflict markers into the user's uncommitted files.

Mount keeps printing the worktree path; the sync/warning happens before the
`cd` instruction.
