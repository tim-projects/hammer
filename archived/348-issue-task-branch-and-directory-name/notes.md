Task: 348-issue-task-branch-and-directory-name

## Status
Implemented on branch `348-issue-task-branch-and-directory-name`. All criteria met.

## Change
1. tasks_ai/utils.py: new derive_task_id(numeric_id, task_type, title) - the one
   naming rule (30-char slug cut, empty slug -> "task"), plus
   worktree_path_matches(wt_path, worktrees_base, branch).
2. tasks_ai/commands/create.py: both id derivations (task id:93 and the --parent
   pair id) now call derive_task_id; 'tasks create' also prints the resolved
   worktree path next to the branch.
3. tasks_ai/commands/doctor.py: expected_br and expected_dir both come from the
   same helper, and a new "worktree path" inconsistency flags a registered
   worktree that is not <worktrees_base>/<branch> (abspath-compared).
4. tests/test_task_naming.py (7 tests): long title, punctuation/case, short
   title, unusable title, and the three worktree-path cases.

## Notes
- The 30-char cap was kept deliberately: it is what every existing task, branch
  and remote already uses, and doctor derives the same string, so changing it
  would only create new names that no longer match the old ones. It is now
  explicit in one place and stated in the helper docstring.
- doctor --fix is unchanged: a worktree-path inconsistency alone does not
  trigger a directory rename (the move guard still requires a wrong folder name
  or state).

## Verification
- End-to-end: ./hammer tasks --dev create "..." prints "Worktree path:
  /tmp/.tasks-repo/.task-worktrees/<branch>" identical to the actual worktree
  hammer created; ./hammer tasks --dev doctor reports "No issues found".
- pytest tests: 5 failed / 169 passed / 1 skipped. Same 5 pre-existing failures
  as the base commit (baseline 5/162/1 on main after 344); +7 are the new tests.
- ./hammer check all: lint, test, typecheck, format all green.
