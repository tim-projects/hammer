CONFIRMED DESIGN — ref-derived task identity.

Authoritative high-water sources (scanned together):
1. Task-record folders across all STATE_FOLDERS in .tasks/ (primary). Records are permanent: cleanup.py removes worktrees and merged branches only; ARCHIVED records stay. Covers REJECTED too.
2. Branch refs matching ^(\d+)- : local refs/heads plus remote-tracking refs/remotes/* (secondary, covers the 315-class stray branches whose record is gone and any externally pushed branch).

Allocation: allocate_task_id(count=1) returns [max(sources)+1 ... +count], executed inside ONE store_lock transaction that also covers the caller's record write — create must open the lock once and allocate + write both the parent and (when paired) the test-child record inside it. count>0 exists because create allocates twice today (parent + test-pair child); a pure per-call max-scan would hand out the same id twice.

Persistence: the task record itself (folder name + meta.json Id). No counter file, no hash files, no recovery heuristic — a fresh clone rebuilds the high-water from the store scan. Guard's SQLite refs table stays a verifier, never an allocator (plan-guard.md R7 resolved: store-derived allocation + guard rejection).

Never-reuse rule: records are permanent. 378/379-style automated cleanup may remove worktrees/branches; it may never delete a record. If a record is ever lost, refs (source 2) keep the id above reuse, and guard REJECTs duplicates at gates.

Cross-machine: two machines sharing the store via push/pull can still collide — identical exposure to the counter today (not a regression). Backstop unchanged: the guard gate. Known limitation, stated.

Migration for task 495: land the allocator first with a floor = max(sources, .task_counter value while the file exists); 495 then deletes counter.py, the cli helper call sites (_get_next_id, _verify/_recover/_write hash helpers), doctor's stale-counter block, and the four tests that seed the file (plan-guard.md F14: test_tasks.py, test_init_backup.py, test_audit_verify_integration.py, test_robustness.py). Rollback: re-enable the counter read (the allocator is additive first).

Rejected alternates: (a) guard SQLite as allocator — disposable cache, adds a rebuild dependency at create time; (b) git-branch creation as the reservation (R7's option) — mints refs for lazy tasks before they have a branch (455 lazy creation), and is blind to REJECTED records whose branch was deleted; (c) counter kept as a hint — keeps the mutable file 495 exists to delete.
