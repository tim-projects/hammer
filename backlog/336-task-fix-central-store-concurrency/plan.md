1. Grep for the store-mutation helper added by task 328 and reuse it; if it does not exist yet, land 328 first (defect 4 depends on it)
2. Defect 1: wrap counter read-increment-write-hash-commit in the shared lock; add racing-allocate test
3. Defect 2: route all manifest mutations through one locked helper; add concurrent-mount test
4. Defect 3: replace the is_merged fast-track with an ahead-of-main requirement; move fetch out of the gate; add zero-commit and merged-branch tests
5. Defect 4: exact path matching and per-task commit history in undo; temp files outside the store; add sibling-id and sibling-task-commit tests
6. Run ./hammer check all; move task through pipeline
7. Fix central-store concurrency hazards: id allocation, manifest race, merge gate, undo scoping