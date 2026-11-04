---
Task: 312-issue-guard-refs-cache-must-not-clob
---


- Progress: fix + regression tests carried over and verified; 22/22 green.

## Why this task exists (supersedes 249)

Task 249 carried this exact fix, but its numeric id collided with a pre-existing
stale branch `249-task-repair-pipeline-codebase-corru` (already merged to main,
no task folder). The guard correctly rejected the merge:

```
GUARD_DUPLICATE_ID: multiple local branches claim id 249:
  249-issue-guard-refs-cache-clobbers-loca, 249-task-repair-pipeline-codebase-corru
```

`--force` could not resolve it, because `move.py` skips the git merge whenever
`force` is set — so forcing flips the state but never merges the code.

Rather than delete history or bypass the gate, this task was created with a
clean id (312) and the verified fix was copied onto it. Task 249 is then moved
to REJECTED (its branch carries no merged work).

Note: the task counter was also stale (250) against 60 existing branch ids
(251-310), so any new task would have landed on a colliding id. It was bumped
to 311 using the same mechanism `doctor --fix` uses for stale counters, but
accounting for branch ids as well as task folders. This is bookkeeping so id
minting stays unique; it does not hide any error.

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

A local branch and its `origin/` twin collided on one key and the remote entry
silently replaced the local one. The same collision hit the SQLite `refs` table
(`refname` is PRIMARY KEY), so the lookup in `verdict()` —
`SELECT 1 FROM refs WHERE refname=? AND kind='branch'` — returned no row for any
branch that had been pushed.

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
reading its own wrong cache, not git. `hammer guard refresh` did not fix it:
refresh re-derived the same colliding map, so the verdict was unchanged.

### Secondary defect fixed alongside

`_current_tasks_ref()` looks up `TASKS_REF_REMOTE` (`"origin/tasks"`) first, which
**could never match** under the old short-name keying; it silently fell through
to `TASKS_BRANCH` (`"tasks"`), which the collision had overwritten with the
*remote* object. Both the preference and the object were wrong. After the fix,
`origin/tasks` and `tasks` are distinct entries with distinct objects.

## Fix

1. `_live_refs()`: remote entries are now keyed `"<remote>/<branch>"`
   (e.g. `origin/tasks`, `origin/248-...`), so a remote twin can never
   overwrite its local branch.
2. `task_id_of()`: ignores a leading remote prefix before reading the leading
   task id, so `GUARD_DUPLICATE_REMOTE_ID` / `GUARD_REMOTE_DIVERGENCE` and the
   `guard.py --fix-plan` path keep working with the new keying.

No schema change; `refresh()` does `DELETE FROM refs` + full re-insert, so no
stale short-name rows survive, and `rebuild` wipes the DB outright.

Effect on this repo: `branch`-kind rows went **154 -> 240**; `main` is now
`branch` with its `origin/main` twin preserved alongside it.

## Verification

Regression tests in `tests/test_guard.py` (class `TestGuardRefs`):

- `test_remote_twin_does_not_hide_local_branch` — dict keeps both rows
- `test_current_branch_keeps_local_kind` — `main` stays `branch`
- `test_refs_table_holds_local_and_remote_rows` — DB holds both kinds after rebuild
- `test_promoted_task_with_pushed_branch_is_not_rejected` — no `GUARD_BRANCH_MISSING`

**These four tests were confirmed to FAIL against the unfixed code** (checked out
the pre-fix `guard_engine.py`, ran the class, saw all 4 fail with
`('...', 'remote') != ('...', 'branch')`), then re-applied the fix and confirmed
they pass.

- `tests/test_guard.py`: **22 passed** (18 pre-existing + 4 new), re-run in this
  worktree after the copy.
- `ruff check` clean on both files.
- Full suite on the equivalent branch 249 previously: 6 failed / 109 passed /
  1 skipped = main's 87 baseline + 22 guard tests; the 6 failures are the
  pre-existing baseline (243/245). Re-verified here as 22/22 in the file.

## Shortcut notes

- `shortcut:` the tests simulate a pushed twin with
  `git update-ref refs/remotes/origin/<branch>` rather than a real push, because
  the fixture has no safe writable remote. It exercises the exact code path
  (the ref-name collision) without network side effects.