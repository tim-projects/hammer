CONFIRMED DESIGN — ref-derived task identity.

## Authoritative high-water sources (scanned together)

1. **Permanent task records (primary).** Scan the numeric ID prefix of every task-record folder across all `STATE_FOLDERS` in the `.tasks` store and the `Id` in each record's `meta.json`. Records are permanent: `tasks_ai/commands/cleanup.py` prunes stale worktree manifest entries, deletes merged branches, and removes merged task worktrees; it never deletes task-record folders. ARCHIVED and REJECTED records therefore remain part of the high-water.
2. **Git branch refs (secondary).** Run `git for-each-ref refs/heads refs/remotes` and parse each branch component matching `^(\d+)-`; local `refs/heads/*` and remote-tracking `refs/remotes/*` are both included. This covers stray branches whose task record is gone and externally pushed task branches.

The allocator uses `max(records, refs)` as its high-water. During the additive migration it also uses the existing `.task_counter` value as a floor. A fresh clone rebuilds the high-water from the store records and refs; no counter, hash file, or recovery heuristic is required for the final design.

## Allocation and locking

`allocate_task_id(count=1)` returns `[max(sources) + 1, ..., max(sources) + count]`.

Allocation and the caller's record write occur inside **one** `store_lock` transaction. A paired create must open the lock once, allocate the parent and test-pair child together (`count=2`), and write both records while that lock is held. A separate scan per allocation would return the same ID twice within the same transaction.

The current counter implementation demonstrates the required serialization boundary: `TaskCounterProtector.get_next_id()` holds `store_lock` around its whole read-modify-write-commit operation. The new allocator keeps that lock boundary but derives the high-water from records and refs.

## Lazy tasks and never-reuse rule

BACKLOG and READY tasks may have no branch yet. Their permanent records are sufficient for allocation from the primary source.

Records are never deleted by automated cleanup. Cleanup scope is limited to worktrees and merged branches. If a record is ever lost, surviving branch refs keep its ID above reuse; if both are lost, the guard rejects duplicate IDs at pipeline gates.

## Concurrency and cross-machine behavior

Intra-repository allocation is serialized by `store_lock`, covering both allocation and record writes. Two machines sharing the store through push/pull can still collide, which is the same exposure as the current mutable counter and not a regression. The guard remains the cross-machine backstop and rejects duplicates at gates.

## Migration and rollback

Land the allocator first, additively, with `high_water = max(records, refs, counter_value)` while `.task_counter` exists. Task 495 then deletes the counter file, `counter.py`, the CLI counter/recovery/hash helpers, doctor's stale-counter block, and the tests that seed the counter. Task 501 builds its creation-time uniqueness check on the allocator's ref scan. Only after those changes may task 495 retire the counter.

Rollback is to re-enable the counter read while leaving the allocator in place; the new allocator is additive first.

## Rejected alternatives

- **Guard SQLite as allocator:** the cache is disposable and would add a rebuild dependency to creation.
- **Git branch creation as reservation:** it mints refs before lazy tasks have branches and misses REJECTED records whose branch was deleted.
- **Counter retained as a hint:** this keeps the mutable file that task 495 exists to delete.

## Implementation tasks and acceptance tests

- **Task 509:** implement the record-and-ref allocator, counter migration floor, and one-lock paired create.
- **Task 510:** add user-level coverage for the allocator.
- Acceptance tests: N concurrent create processes in `--dev` mode allocate unique IDs; a fresh clone agrees with the original store's allocation high-water; reject-then-create never reuses the rejected ID.
