Implement the confirmed task-507 design.

Allocator API: `allocate_task_id(count=1)` scans permanent task-record folders across all `STATE_FOLDERS` and local plus remote-tracking Git refs whose branch component starts with `^(\d+)-`. The combined maximum is the high-water; return `max + 1` through `max + count`.

The existing `.task_counter` value is a migration floor while it exists. The combined high-water is `max(records, refs, counter)`. Guard's SQLite refs cache remains verification-only and must not allocate IDs.

Allocation and the caller's record writes share one `store_lock` transaction. A paired create must allocate the parent and test child together (`count=2`) or otherwise cover both writes in one lock, so concurrent processes cannot receive duplicate IDs.

Records remain permanent across BACKLOG, READY, PROGRESSING, TESTING, REVIEW, STAGING, PR, PROVISIONING, DONE, ARCHIVED, and REJECTED. Cleanup removes worktrees and merged branches, not records. Refs provide a secondary high-water if a record is lost. Cross-machine collisions remain possible until guard rejects the duplicate at a gate.
