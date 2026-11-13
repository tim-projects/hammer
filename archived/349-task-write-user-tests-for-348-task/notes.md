Task: 349-task-write-user-tests-for-348-task

## Status
Implemented on branch `349-task-write-user-tests-for-348-task`. Criterion met.

## Change
tests/test_task_naming_user.py (5 tests), driving the hammer CLI in the --dev
fixture repo the way a user does:
- test_branch_folder_and_worktree_share_one_name: the created task's folder in the
  store, the git branch, the worktree directory and the -j payload's
  branch/worktree fields are one identical name.
- test_a_long_title_is_cut_the_same_way_everywhere: a long title yields a slug at
  the cap, and the worktree basename equals the folder name (no second spelling).
- test_create_prints_the_worktree_path: the human-readable create output prints
  "Worktree path: <...>" under the repo's .task-worktrees, matching the printed
  "Worktree branch:" name and existing on disk.
- test_current_shows_the_worktree_path_in_json_and_text: `tasks current <id>`
  reports the worktree path in both the -j payload and the text output.
- test_doctor_reports_a_worktree_registered_at_the_wrong_path: after renaming the
  registered worktree directory, `tasks doctor` reports the drift and names the
  actual path.

## Verification
- pytest tests/test_task_naming_user.py: 5 passed.
- Full suite run below; ./hammer check all must pass before promotion.
