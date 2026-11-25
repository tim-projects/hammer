Repro (verified read-only, 2026-11-24), from the 489 task worktree:

    ../../hammer repo merge 489 provisioning -y
    FileExistsError: [Errno 17] File exists:
    '/home/vscode/git/tasks-ai/.task-worktrees/489-task-key-repo-merge-plumbing-to-the/.git'

Traceback path: `repo.py:346` (`merge_lock(repo_root())`) -> `utils.py:44`
(`os.makedirs(os.path.dirname(path), exist_ok=True)`).

Root cause: `merge_lock` joins `repo_root` + `/.git`. In a linked worktree
`.git` is a file, not a directory. Callers disagree on what root means:
`git_service.py:431` passes `context.main_repo_root` (correct today, so
pipeline-internal merges work), `repo.py:346` passes `repo_root()` = the
invoked top-level (the worktree, when driven from one). Both must resolve to
the SAME file or the lock is not shared.

Fix: resolve the git common dir from the supplied root:

    git rev-parse --git-common-dir    # relative output -> join against
                                      # os.path.abspath(root), then normpath

House pattern to copy (do not reinvent): `tasks_ai/context.py:123-136`
(`ProjectContext._get_main_repo_root`) and `guard_engine.py:171-180`
(`GuardEngine._main_repo_root` / `_resolve_cache_dir`). Both run
`--git-common-dir` from the caller's cwd and normalize relative output.

Verified behavior on this machine:
- from the 489 worktree: `/home/vscode/git/tasks-ai/.git` (absolute)
- from the main checkout: `.git` (relative -> must be joined, not used raw)

Do NOT use `git rev-parse --absolute-git-dir`: from a linked worktree it
returns the per-worktree dir `.git/worktrees/<name>`, which reintroduces split
locks. Verified.

Keep `<root>/.git` as the fallback when git fails, so off-repo callers behave
exactly as before. After the fix the common git dir always exists, so the
`os.makedirs` call goes away.

No stale-lock cleanup needed: the failing path never created a file (verified:
no `hammer-merge.lock` under `.task-worktrees/` or in the main `.git`).

Sequencing constraint: land on main BEFORE task 489's funnel merge
(`repo merge 489 provisioning`), because 489-PR's copy of
`tasks_ai/utils.py` still carries the bug and the merge must run from 489's
worktree with the fix synced in.