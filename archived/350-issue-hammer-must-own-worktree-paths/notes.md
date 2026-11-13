Task: 350-issue-hammer-must-own-worktree-paths

## Status
Implemented on branch `350-issue-hammer-must-own-worktree-paths`. All criteria met.

## Change
1. tasks_ai/utils.py: audit_worktree_manifest(manifest, worktrees_base, live_paths) -
   the single ownership rule. Findings:
     GUARD_WORKTREE_UNREGISTERED     dir under the base not in the manifest
     GUARD_WORKTREE_PATH_DRIFT       registered path != <base>/<branch> (or no path)
     GUARD_WORKTREE_MISSING_WORKTREE registered path is not a git worktree
2. tasks_ai/worktree_manager.py: live_worktree_paths() (parses
   `git worktree list --porcelain`) and audit_worktrees(), plus
   remove_unregistered_dir() which only deletes a directory that no manifest
   entry registers and that is not a live worktree and that lives under the base.
3. tasks_ai/guard_engine.py: GuardEngine._main_repo_root()/_worktrees_base()
   (via --git-common-dir, worktree-safe) and the audit wired into
   _compute_anomalies, so the same findings reach guard scan and every gate.
4. tasks_ai/commands/doctor.py: audits and reports the same findings; with --fix
   it removes unregistered stray directories and logs each removal.
5. tasks_ai/commands/current.py: worktree_path in the -j payload and in the
   human output, so `tasks current` answers "where is this task's worktree".
6. data/hints.json + data/errors.json: human message + fix plan per new code.
7. tests/test_worktree_path_ownership.py (10 tests).

## Verified live
- Stray dir `.task-worktrees/999-task-does-not-exist` -> `hammer guard scan`
  reports GUARD_WORKTREE_UNREGISTERED naming the path; `hammer tasks doctor`
  reports it; `doctor --fix` removes it and a follow-up doctor is clean.
- `hammer tasks current 350` -> "- **Worktree**: <main>/.task-worktrees/<branch>".
- Two bugs found and fixed while wiring: the guard parsed `worktree` where the
  porcelain parser stores `path`, and the base was taken from
  _worktree_list()[0], which is the *current* worktree, not the main checkout.
- pytest tests: 5 failed / 179 passed / 1 skipped (same 5 pre-existing failures;
  +10 new). ./hammer check all green.

## Pre-existing drift now visible (not fixed here)
`guard scan` reports `.task-worktrees/.tasks` as an unregistered directory and
GUARD_WORKTREE_ORPHAN for task 315 (two worktrees). Both predate this change;
they block nothing (the stray has no task id), and repairing them belongs to
their own tasks.
