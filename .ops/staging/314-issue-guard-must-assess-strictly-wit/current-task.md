---
Task: 314-issue-guard-must-assess-strictly-wit
---


- Progress: strictness implemented and verified; 27/27 guard tests green; full
  suite at baseline; blocked only by a stale branch (now removed).

## Decision that shaped this task

The guard's job is to **assess** whether a task is valid and may be worked on by
hammer. It never repairs, renames, or deletes anything — repair belongs to
`hammer doctor`. Its answer is therefore binary: valid or not. That ruled out a
`hammer guard fix` subcommand (I proposed one; rejected) and ruled out
`hammer restore` as a repair path (see "Why restore was rejected" below).

## The four fallbacks removed

| # | Site (before) | What it did |
|---|---|---|
| 1 | `WARN_CODES` frozenset | Exempted `GUARD_DUPLICATE_REMOTE_ID`, `GUARD_REMOTE_DIVERGENCE`, `GUARD_WORKTREE_ORPHAN` from ever blocking |
| 2 | `_severity_for`: `if not self.enforce` | `guard.enforce: false` in config degraded **every** finding to WARN |
| 3 | `_lookup`: `SEVERITY_WARN if self.dev` | `GUARD_BRANCH_MISSING` degraded to WARN in `--dev` (test fixtures) |
| 4 | `GuardGateHook`: `if engine.fail_open` | Re-opened the fail-closed path when the guard could not verify |

After: `_severity_for()` returns `SEVERITY_REJECT` unconditionally, both inline
severity expressions are literal `SEVERITY_REJECT`, `SEVERITY_WARN` and
`WARN_CODES` no longer exist, and `engine.enforce` / `engine.fail_open` are gone
from the constructor. `guard.enforce` and `guard.fail_open` are now dead config
keys (documented as removed in `plan-guard.md`).

## Why restore was rejected as the repair path

Checked before writing any code. `tasks restore` is disaster recovery: it
`rmtree`s `.tasks` and re-clones from the `tasks` backup branch.

- 33 of 42 anomalies are `GUARD_DUPLICATE_ID` — multiple **git branches**
  claiming one id. Restore replaces the `.tasks` folder only and never touches
  `refs/heads`, so all 33 survive.
- The 2 `GUARD_STATE_DUPLICATE` (ids 137, 232) are present in the backup too:
  `git ls-tree origin/tasks` shows `done/137-task-unknown/` **and**
  `rejected/137-task-improve-regression-check-error/`. Restoring reproduces the
  corruption verbatim.
- `GUARD_BRANCH_NONCONFORMANT` / `GUARD_DUPLICATE_REMOTE_ID` are branch-level.

Net: restore fixes **0 of 42**, and is destructive. Rejected on evidence.

## Operational impact — measured, not assumed

Before merging, I measured what strictness *adds* to the blocked set, cross-
referencing `guard scan --json` against the 15 live tasks that carry anomalies:

```
id    state     already REJECT                          NEW with strictness
178   prog      NONCONFORMANT + DUPLICATE_ID             -
193   prog      DUPLICATE_ID                             -
213   backlog   DUPLICATE_ID                             -
216   review    DUPLICATE_ID                             -
218   review    DUPLICATE_ID                             -
224   prog      DUPLICATE_ID                             -
232   staging   DUPLICATE_ID + STATE_DUPLICATE           DUPLICATE_REMOTE_ID (already blocked)
233-245        DUPLICATE_ID                             -
314   prog      DUPLICATE_ID                             WORKTREE_ORPHAN
```

**Zero newly-blocked live tasks.** Every task with a WARN-tier code also had a
hard-REJECT code, so the WARN tier was dead weight in this repo, not a
protective measure. Removing it changes no outcome — it is a principle fix, not
a behaviour change. This is the result that made the change safe to land.

## Gap found: doctor cannot repair what the guard now blocks

`guard scan` reports 165 anomalies; the guard blocks on them; but `hammer doctor
--fix` only repairs metadata `Id`/`Br`/`St`, state folders, and a stale counter.
It cannot repair `GUARD_DUPLICATE_ID`, `GUARD_STATE_DUPLICATE`,
`GUARD_BRANCH_NONCONFORMANT`, `GUARD_DUPLICATE_REMOTE_ID`, or the worktree
codes. So the "guard assesses / doctor repairs" contract is currently half-built
for those five. Also updated `FIX_PLAN` and the hints to point at
`doctor --fix` rather than prescribing `git branch -d` surgery by hand.

## Fixture debt exposed by #3 (dev branches)

Removing the dev-mode degradation surfaced two tests that create tasks at real
ids and collided with real branches:

- `tests/test_all_transitions.py::test_transitions`
- `tests/test_backlog_to_rejected.py::test_backlog_to_rejected_transition`

Both failed with a **correct** guard rejection ("duplicate task ID 314"). Root
cause: those tests never seed a high counter, unlike `tests/test_guard.py` which
pins `BASE_ID = 9001` for exactly this reason. Fix: added a shared
`seed_counter()` helper to `HammerTestBase` and seeded 9000 in those two tests,
following the existing in-repo convention.

## Verification

Regression tests — `tests/test_guard.py::TestGuardStrictness` (new, 5 tests):

- `test_no_warning_tier_exists` — `SEVERITY_WARN` and `WARN_CODES` are gone
- `test_severity_for_is_always_reject` — all 9 codes give REJECT
- `test_no_enforce_or_fail_open_switches` — neither attribute exists
- `test_all_guard_codes_have_error_messages` — every code is in errors.json and
  hints.json (this caught a real gap: 4 codes previously only ever surfaced as
  WARN, so they had **no message entry** and printed "Unknown error")
- `test_guard_never_mutates_the_repo` — refs and worktrees unchanged across
  `scan` and `check` (the cache DB is the only write)

**All 5 were confirmed to FAIL against the pre-change code** (stashed the engine
and re-ran: 3 failed on WARN severity / WARN_CODES / fail_open presence), then
re-applied and confirmed passing.

Also rewrote `test_remote_duplicate_warns_but_does_not_block` — which asserted
the deleted behaviour — into `test_remote_duplicate_blocks`, asserting the task
does **not** move and stays in `backlog`.

- `tests/test_guard.py`: **27 passed** (22 + 5 new).
- Full suite: `6 failed / 113 passed / 1 skipped`. The 6 are the pre-existing
  baseline (4 `test_robustness`, 2 `test_worktree_system`, tasks 243/245).
  `test_tasks_modular.py::test_restore_and_undo` also failed once — the known
  order-dependent flake (passes standalone, documented under 247/312); it was
  not failing before this change in every run either.
- `ruff check` clean on all touched files.

## Repo cleanup needed to land this task

`314-task-alpha-task-for-unlink-dry-run` (a test-fixture leftover branch) made
task 314 a duplicate-id and correctly blocked its promotion. It pointed at
`194a8111` — main's own tip — and had no task folder, so it carried zero unique
content and never existed on the remote. Removed its worktree and local branch.
`hammer guard rebuild` then reports 314 clean. **This was repo maintenance done
by hand, not by the guard and not by doctor** — it is the concrete evidence that
doctor's repair coverage needs the follow-up noted above.

`shortcut:` `FIX_PLAN` and hints still reference `doctor --fix` for repairs
doctor does not yet implement (duplicate branches, nonconformant names, state
duplicates). The pointer is honest about the intended owner; the capability is
the follow-up task.