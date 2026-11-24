---
Task: 489-task-key-repo-merge-plumbing-to-the
---

- Progress: ## Implementation status

Task 489 implementation is complete on task branch `489-task-key-repo-merge-plumbing-to-the` / stage ref `489-PR`.

Completed work:

- Retargeted the `repo.py` shared funnel from `testing -> staging -> default` to `provisioning -> default`.
- Numeric task merges use the `<id>-PR` stage ref, merge it into `provisioning`, and then move the task to `PROVISIONING` so the stage-ref gate passes.
- `check-merged` and `check-merged-testing` resolve task IDs and check ancestry from `provisioning`.
- Missing `provisioning` branches bootstrap from `<remote>/<default>` with a local-default fallback.
- `repo sync` advances `provisioning` into the default branch.
- Added `provisioning` to the local and remote deletion guards; retained `testing` and `staging` as protected historical branches.
- Added focused provisioning-funnel coverage and updated existing pipeline/deletion expectations.

Validation completed before the blocker:

- Focused suites: `34 passed` (`tests/test_repo_provisioning.py`, `tests/test_critical_branches.py`, `tests/test_hooks_default_branch.py`, `tests/test_repo_worktree_root.py`, `tests/test_merge_lock_guard.py`).
- `./hammer check all`: lint PASS, test PASS, typecheck PASS, format PASS.
- Review completed for all 5 generated patches.
- Audit, verification, and regression check completed successfully.
- All three acceptance criteria are genuinely implemented and marked complete.

## Production-path blocker

Timestamp: 2026-11-24T17:39:53+00:00

Task state when blocked: `PR`.

Command attempted from the task worktree:

```bash
cd .task-worktrees/489-task-key-repo-merge-plumbing-to-the
../../hammer repo merge 489 provisioning -y
```

Exact failure:

```text
Traceback (most recent call last):
  File "/home/vscode/git/tasks-ai/repo.py", line 738, in <module>
    sys.exit(main() or 0)
             ~~~~^^
  File "/home/vscode/git/tasks-ai/repo.py", line 708, in main
    cmd_merge(args.src, args.dest)
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~^
  File "/home/vscode/git/tasks-ai/repo.py", line 346, in cmd_merge
    with merge_lock(repo_root()):
          ^^^^^^^^^^^^^^^^^^^^^^^
  File "/usr/lib/python3.13/contextlib.py", line 141, in __enter__
    return self.gen()
           ^^^^^^^^^^^^^
  File "/home/vscode/git/tasks-ai/tasks_ai/utils.py", line 44, in merge_lock
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
FileExistsError: [Errno 17] File exists: '/home/vscode/git/tasks-ai/.task-worktrees/489-task-key-repo-merge-plumbing-to-the/.git'
```

Root cause:

1. The command ran from the linked task worktree `/home/vscode/git/tasks-ai/.task-worktrees/489-task-key-repo-merge-plumbing-to-the`.
2. `repo.py::repo_root()` resolves the invoked git top-level, which is the linked task worktree.
3. `tasks_ai/utils.py::merge_lock(repo_root)` constructs `<repo_root>/.git/hammer-merge.lock` and calls `os.makedirs()` on the parent directory.
4. In a linked worktree, `.git` is a regular file pointing to the main repository's common git directory, not a directory. `os.makedirs(..., exist_ok=True)` therefore raises `FileExistsError` before acquiring the lock.
5. The shared merge lock must live in the main repository's common git directory (`/home/vscode/git/tasks-ai/.git/hammer-merge.lock`), or the caller must pass the main repository root instead of the linked worktree root.

Important invocation detail:

- `../../hammer` resolved the main checkout's wrapper and loaded `/home/vscode/git/tasks-ai/repo.py`, as shown by the traceback.
- After fixing the lock-root bug, rerun the funnel merge using the task worktree's own `./hammer repo merge 489 provisioning -y` so the task branch implementation is the code exercised.

Impact and safety state:

- Failure occurred while acquiring the merge lock, before branch resolution, provisioning bootstrap, merge, push, or task-state transition.
- No partial merge occurred.
- Read-only verification after the failure showed no local `provisioning` branch, no `origin/provisioning` branch, and `489-PR` was not merged anywhere.
- Task 489 remains safely in `PR`; the validated implementation and stage refs are preserved.
- No user data or shared refs were changed by the failed command.

Recommended recovery:

1. Fix shared merge-lock root resolution so linked worktrees use the common git directory or main repository root.
2. Add a regression test that runs `repo merge` from a linked task worktree and proves the lock serializes merges without the `.git` file/directory collision.
3. Rerun focused tests and `./hammer check all`.
4. From the task worktree, run `./hammer repo merge 489 provisioning -y`.
5. Verify `check-merged 489` exits 0 and task 489 enters `PROVISIONING`.
6. Continue the pipeline through `DONE`.
- Findings: 
- Mitigations: 
