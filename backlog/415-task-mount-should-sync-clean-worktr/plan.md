1. 1. Move the fetch+merge+abort flow from WorktreeSyncHook into a reusable
2.    git_service method; the hook calls it (behavior unchanged) and mount uses it.
3. 2. Add git_service conflict detection via `merge-tree --write-tree` returning
4.    conflicted paths, plus a "has local work" check (porcelain + rev-list).
5. 3. Call both from mount.py: sync when there is no local work, otherwise warn
6.    with the conflict list.
7. 4. Add tests in the dev fixture repo using tests/hammer_test_base.py.
8. 5. Run ./hammer check all.