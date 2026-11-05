[2026-11-05 06:44:56] Task created to close the repair gap between guard and doctor.

## Evidence for why this task exists

### 1. The guard is now strict (task 314, merged to main at `2ae49a37`)

The guard's warning tier was removed entirely: `WARN_CODES`, `SEVERITY_WARN`,
`guard.enforce` (config kill switch), the `self.dev` degradation, and
`guard.fail_open` are all gone. Every finding blocks. Confirmed on main:

```
$ git show main:tasks_ai/guard_engine.py | grep -c "WARN_CODES\|SEVERITY_WARN\|self.enforce\|fail_open"
0
$ hammer guard check 232 --to DONE
GUARD_DUPLICATE_ID: multiple local branches claim id 232: ...
GUARD_DUPLICATE_REMOTE_ID: multiple remote branches claim id 232: ...
GUARD_STATE_DUPLICATE: id 232 exists in 2 state folders: staging/..., done/...
```

Note the absence of the old `[guard] WARN:` prefix — every line is now a hard
rejection.

### 2. But `hammer doctor --fix` cannot repair what the guard blocks

`tasks_ai/commands/doctor.py --fix` repairs only:

- `metadata.Id` / `metadata.Br` / `metadata.St` mismatches
- moving a task directory into its metadata-correct state folder
- a stale `.task_counter`

It has **no repair** for `GUARD_DUPLICATE_ID`, `GUARD_STATE_DUPLICATE`,
`GUARD_BRANCH_NONCONFORMANT`, `GUARD_DUPLICATE_REMOTE_ID`,
`GUARD_REMOTE_DIVERGENCE`, or the worktree codes. So the guard blocks on 165
anomalies that the repair tool cannot fix.

### 3. The cost is already real, not hypothetical

To land task 314 I had to remove a stale fixture branch
(`314-task-alpha-task-for-unlink-dry-run`, already at main's tip, no task
folder, zero unique content) **by hand** with `git worktree remove` +
`git branch -D`, because neither the guard (by design — it assesses only) nor
doctor (no capability) would do it. Manual surgery is exactly the estate this
project is supposed to have eliminated.

### 4. `hammer restore` is not a substitute

Checked and rejected on evidence: `tasks restore` rmtree's `.tasks` and
re-clones the `tasks` backup branch, so it fixes **0 of 42** anomalies —

- 33 are `GUARD_DUPLICATE_ID` (multiple **git branches**); restore never
  touches `refs/heads`
- the 2 `GUARD_STATE_DUPLICATE` (ids 137, 232) exist in the backup too:
  `git ls-tree origin/tasks` shows `done/137-task-unknown/` **and**
  `rejected/137-task-improve-regression-check-error/`, so restoring reproduces
  the corruption verbatim

### 5. Measured scale of the repair backlog

`hammer guard scan --json` currently reports 165 anomalies, including:

| Code | Count | Repair needed |
|---|---|---|
| `GUARD_DUPLICATE_ID` | 33 | keep the folder-matching branch, remove losers |
| `GUARD_DUPLICATE_REMOTE_ID` | 5 | prune stale remote duplicates |
| `GUARD_BRANCH_NONCONFORMANT` | 2 | rename to `<id>-<type>-<slug>`, fix `Br` |
| `GUARD_STATE_DUPLICATE` | 2 | keep the metadata-correct folder, move the other |
| `GUARD_REMOTE_DIVERGENCE` | ~120 | restore branch from origin or reconcile |

Also 15 live tasks (178, 193, 213, 216, 218, 224, 232–245) carry duplicate ids
and are currently un-promotable until this repair work lands.

## Design constraints to respect

- **Guard assesses, doctor repairs.** Do not add repair to the guard; do not
  weaken the guard so doctor is optional.
- **Dry-run is the default.** `--fix` without confirmation must print the plan
  and change nothing.
- **Never silently destroy unmerged work.** A loser branch may hold the only
  copy of something. Confirm, or clearly report it as unmergeable.
- **Pick the winner by rule, not by whim:** the branch whose name matches the
  live task folder in `.tasks` is canonical.
- **Re-derive the guard cache after any repair**, and print exactly what changed.
- **Report honestly what doctor cannot repair**, so the guard's `FIX_PLAN`
  pointers stay truthful rather than aspirational.
[2026-11-05 06:47:32] Cp
