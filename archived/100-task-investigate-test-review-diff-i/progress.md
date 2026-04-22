# Investigation Progress: test_review_diff_in_dev_mode

## Root Cause Identified

The test fails because `_generate_review_diff()` returns "no changes detected" when generating diffs in dev mode.

### Key Finding
The diff command `git log --patch {main_sha}..{branch}` returns empty when:
1. `main_sha` equals the branch SHA (no commits between them)
2. OR the git repo doesn't have the expected branches

### Test Flow Analysis
1. Test creates temp git repo with `master` as default branch
2. Creates task branch `1-task-dev-review-diff`
3. Makes commit on task branch
4. Creates `testing` branch and merges task into it
5. Moves to REVIEW - this triggers diff generation

### Issue
The test expects the diff to capture commits on the task branch vs `master`. But after merging the task branch into `testing`, the task branch is now the same as `testing` in terms of commit history.

When `_generate_review_diff` runs:
- It gets `default_branch = master`
- It tries `git log --patch {master}..{task_branch}`
- But since the task branch was merged into testing (which was based on master), there are no new commits on the task branch that aren't in master

### Evidence
- Test output shows `initial_branch = master`
- Git merge shows "Fast-forward" - meaning testing branch now points to same commit as task branch
- No diff detected because branch is merged

### Possible Fixes
1. Test should NOT fast-forward merge task branch into testing
2. OR test should make additional commits AFTER the merge
3. OR diff generation should look at different range

## Status: Root cause identified - task branch fast-forwarded into testing during test setup
