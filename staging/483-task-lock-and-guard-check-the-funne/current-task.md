---
Task: 483-task-lock-and-guard-check-the-funne
---


- Progress:
  - Added a kernel-released, reentrant `merge_lock` at `<main_repo_root>/.git/hammer-merge.lock` and applied it to `GitService.merge_branches` and `repo.py merge` across checkout, pull, merge, and push.
  - Added fail-closed branch guard integration before merge; branch-only `guard check --branch` now resolves the task id and reports REJECT findings.
  - Added focused tests for concurrent provisioning merges, duplicate-ID refusal in both service and repo paths, and SIGKILL lock release.
  - Verification: focused acceptance tests `4 passed`; related suite `48 passed, 3 subtests passed`; `./hammer check all` passed lint, test, and typecheck; formatting passed after running Ruff on the new test file.