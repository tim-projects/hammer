---
Task: 511-task-make-the-id-allocator-self-loc
---

- Progress: Implemented self-locking ref-derived allocator, direct create allocation, and transitional counter mirror in counter.py. Added lock/reentrancy and guard-no-allocation regression coverage. Focused tests passed (44); ./hammer check all passed.
- Findings: allocate_task_id now acquires the reentrant store lock itself, so direct and nested callers are safe. TaskCounterProtector was removed; counter.py retains mirror_counter_floor for task 495.
- Mitigations: The outer create lock remains one transaction; nested allocator acquisition uses the existing per-thread reentrancy. No new dependency or migration.
