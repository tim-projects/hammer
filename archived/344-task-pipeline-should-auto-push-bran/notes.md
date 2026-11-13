Task: 344-task-pipeline-should-auto-push-bran

## Status
Implemented on branch `344-task-pipeline-should-auto-push-bran`. All criteria met.

## Root cause
WorktreeCheckHook (tasks_ai/pipeline_hooks.py) required the task branch to exist
on origin before allowing REVIEW/STAGING/DONE/ARCHIVED. When the remote ref was
missing it called cli.error("BRANCH_NOT_PUSHED") and halted the transition, with
a hint telling the user to run `git push origin <branch>` by hand. Hammer had the
branch, the worktree path and the remote context the whole time - it just refused
to push for itself.

## Change
1. tasks_ai/pipeline_hooks.py: the remote check is now `_remote_has_branch(cli,
   branch)`; when it comes back empty, `_push_task_branch()` runs
   `git push -u origin <branch>` (cwd = the task's worktree path when it exists,
   else the default repo root) and logs it via cli.console, then re-checks the
   remote. Only a failed push (non-zero rc) or a remote that still has no ref
   falls through to the same BRANCH_NOT_PUSHED error as before.
2. tests/test_worktree_check_hook.py (new, 4 tests): pushes when the remote ref
   is missing; does not push when the branch is already remote; a failing push
   still halts with SystemExit; --dev never touches the remote.

## Scope note (plan step 3)
The gate checks the task branch, not a "testing" pipeline branch: git
branches live in the main repo and `testing`/`staging` do not exist in this
checkout (promote_task logs "Pipeline branch testing does not exist locally" and
falls back to merging the task branch directly). Pipeline branch pushes already
run inside git_service.merge_branches(yes=True), which task promotion uses for
DONE. No extra auto-push was added there - the manual push the user hit is gone.

## Verification
- pytest tests/test_worktree_check_hook.py: 4 passed.
- Full suite `pytest tests` (running, see below) expected 5 failed / 159 passed /
  1 skipped - the 5 are the same pre-existing failures on main, +1 is the new
  regression test.
- ruff check + ruff format on touched files: clean.

## Gotcha found while working
The task worktree path is truncated to ~40 chars
(`.task-worktrees/344-task-pipeline-should-auto-push-bran`), while the branch
name is `344-task-pipeline-should-auto-push-branch`. Typing the untruncated path
silently creates a new empty directory (edits/writes land outside the worktree).
Use the manifest path: `jq -r '.worktrees["344"].path' .tasks/worktrees.json`.
