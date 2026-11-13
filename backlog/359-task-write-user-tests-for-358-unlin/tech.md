Six store commits still use unscoped 'git add --all' in the shared .tasks repo, bypassing commit_task_paths (the scoped, fail-loud, locked helper added by tasks 328/336):

- tasks_ai/commands/unlink.py:44 (after editing task metadata)
- tasks_ai/commands/delete.py:59 (permanent delete)
- tasks_ai/commands/doctor.py:248 (auto-repairs)
- tasks_ai/pipeline_hooks.py:315 (ArchivedCommitHook) - AND immediately pushes the store to origin afterwards
- tasks_ai/cli.py:375 (one-off LIVE->DONE migration)
- tasks_ai/cli.py:411 (_clear_delete_marks maintenance sweep)

add --all stages EVERY pending change in the shared store: other agents' uncommitted moves, freshly created task folders, doctor repairs, and even the lock file's neighbors. All of it lands in one commit labeled with this command's own task ('Lk', 'Del', 'Archive [id]', ...).

Why this is unsafe with simultaneous worktrees: (a) commit attribution is destroyed - the store's history can no longer be read per task, and the fast-track gate added by task 336 depends on that correlation; (b) another agent's checkpoint may then find nothing to commit and silently report 'No changes', so its record never lands under its own message; (c) the archive hook then PUSHES that mixed state to origin, propagating it; (d) none of these sites hold the store lock, so they can also interleave with another agent's add/commit index operations.

Fix direction: route every site through commit_task_paths (scoped pathspecs, STORE_WRITE_FAIL on failure, already store-locked). The two whole-store sweep sites (LIVE->DONE migration, clear-delete-marks) legitimately touch the whole store - give them the lock at minimum and say so in a comment; the archive hook must use the task-scoped pathspec BEFORE the push. Do not widen the lock alone: scoping is the fix, the lock only serializes.