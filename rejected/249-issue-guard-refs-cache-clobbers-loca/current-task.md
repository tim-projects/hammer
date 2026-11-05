---
Task: 249-issue-guard-refs-cache-clobbers-loca
---


- Progress: REJECTED — superseded by task 312 (same fix, non-colliding id).

## 2026-11-04 — Rejected: duplicate task ID

This task carried a complete, verified fix for the guard refs cache collision
(see the analysis below — it is accurate and was proven by tests). It reached
STAGING, but it could not be merged:

```
GUARD_DUPLICATE_ID: multiple local branches claim id 249:
  249-issue-guard-refs-cache-clobbers-loca, 249-task-repair-pipeline-codebase-corru
```

The colliding branch `249-task-repair-pipeline-codebase-corru` is **already
merged to main** and has no task folder — it is stale history, not a live task.
There is no sanctioned command to delete such an orphan branch (`reconcile`
only handles branches that have a task; `cleanup` only removes worktrees), and
`--force` cannot be used for a merge because `move.py` skips
`_git_merge_transition` whenever `force` is set — forcing flips the state but
never merges the code.

Resolution: the fix was re-created as **task 312** with a clean, non-colliding
id, moved through the pipeline, and merged to main. That merge also unblocked
task 248's DONE promotion, which was the original reason this bug mattered.

Part of enabling that: the task counter was stale (250) against 60 existing
branch ids (251-310), so any new task would have landed on a colliding id. It
was bumped to 311 using the same mechanism `doctor --fix` uses for stale
counters, extended to also account for branch ids. This is bookkeeping to keep
id minting unique; it hides no error.

This task is rejected, not archived, because its branch carries no merged work.
The code now lives on main via task 312.

## Original analysis (retained for the record)

## Root cause (proven empirically)

`GuardEngine._live_refs()` parsed `git for-each-ref refs/heads refs/remotes
refs/tags` into a dict keyed by the **short ref name**:

```python
if full.startswith("refs/heads/"):
    refs[full[len("refs/heads/"):]] = (obj, "branch")      # key: "main"
elif full.startswith("refs/remotes/"):
    rest = full[len("refs/remotes/"):]
    if "/" in rest:  # strip remote name (origin/)
        refs[rest.split("/", 1)[1]] = (obj, "remote")      # key: "main" -> OVERWRITES
```

A local branch and its `origin/` twin therefore collided on one key and the
remote entry silently replaced the local one. The same collision then hit the
SQLite `refs` table (`refname` is the PRIMARY KEY), so the lookup in
`verdict()` — `SELECT 1 FROM refs WHERE refname=? AND kind='branch'` — returned
no row for any branch that had been pushed.

Evidence on `main` before the fix (`hammer guard refresh`, then query the cache):

```
SELECT refname, kind FROM refs WHERE refname='main'
  ->  main|remote                       (main is the current local branch!)
SELECT kind, COUNT(*) FROM refs GROUP BY kind
  ->  branch|154, remote|233
```

154 local branches existed in git but an equal number of rows landed in
`kind='remote'`: every pushed branch lost its local identity.

### Observed symptom

`./hammer repo merge 248-task-write-user-tests-for-247-imple main` failed:

```
Error: GUARD REJECT: task 248 has no local branch, required for DONE.
branch '248-task-write-user-tests-for-247-imple' missing; DONE requires it
```

while `git branch --list "*248*"` showed the branch present. The guard was
reading its own wrong cache, not git.

`hammer guard refresh` did **not** fix it: refresh re-derived the same colliding
map, so the verdict was unchanged. Only `rebuild` would have masked it
temporarily — and it would immediately recur on the next refresh.

### Secondary defect fixed alongside

`_current_tasks_ref()` looks up `TASKS_REF_REMOTE` (`"origin/tasks"`) first, which
**could never match** under the old short-name keying; it silently fell through
to `TASKS_BRANCH` (`"tasks"`), which the collision had overwritten with the
*remote* object. Both the local/remote preference and the object used were
wrong. Verified after the fix: `origin/tasks` and `tasks` are now distinct
entries with distinct objects.

## Fix

1. `_live_refs()`: remote entries are now keyed `"<remote>/<branch>"`
   (e.g. `origin/tasks`, `origin/248-...`), so a remote twin can never
   overwrite its local branch.
2. `task_id_of()`: ignores a leading remote prefix before reading the leading
   task id, so `GUARD_DUPLICATE_REMOTE_ID` / `GUARD_REMOTE_DIVERGENCE` and the
   `guard.py --fix-plan` path keep working with the new keying.

No schema change; `refresh()` does `DELETE FROM refs` + full re-insert, so no
stale short-name rows survive, and `rebuild` wipes the DB outright.

Effect measured on this repo: `branch`-kind rows went **154 -> 240**; `main` is
now `branch` with its `origin/main` twin preserved alongside it.

## Verification

Regression tests added to `tests/test_guard.py` (class `TestGuardRefs`):

- `test_remote_twin_does_not_hide_local_branch` — dict keeps both rows
- `test_current_branch_keeps_local_kind` — `main` stays `branch`
- `test_refs_table_holds_local_and_remote_rows` — DB holds both kinds after rebuild
- `test_promoted_task_with_pushed_branch_is_not_rejected` — no `GUARD_BRANCH_MISSING`

**These four tests were confirmed to FAIL against the unfixed code** (checked out
the pre-fix `guard_engine.py`, ran the class, saw all 4 fail with
`('...', 'remote') != ('...', 'branch')`), then re-applied the fix and confirmed
they pass. They are real regression tests, not decoration.

- `tests/test_guard.py`: **22 passed** (18 pre-existing + 4 new).
- `ruff check` clean on `tasks_ai/guard_engine.py` and `tests/test_guard.py`.
- Full suite `python3 -m pytest tests/` on branch 249:
  **6 failed / 109 passed / 1 skipped** — exactly the pre-existing baseline
  (4 `test_robustness`, 2 `test_worktree_system`, tracked by 243/245).
  Arithmetic check: main has no `tests/test_guard.py`, so its 87 passed plus
  this branch's 22 guard tests = 109. Zero new failures, and no test flipped.
  (`test_restore_and_undo` passed in this run; it is the known order-dependent
  flake documented under task 247.)

## Shortcut / follow-up notes

- `shortcut:` the tests simulate a pushed twin with
  `git update-ref refs/remotes/origin/<branch>` instead of a real push, because
  the fixture has no safe writable remote. It exercises the exact code path
  (the ref-name collision) without network side effects.
- `test_verdict_is_fast_enough_for_a_gate` remains in the suite and passes;
  the extra local rows do not slow the gate.