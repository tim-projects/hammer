

Task: 80-task-fix-promote-tool-workflow-gate

## Progress
- Implementation of Review Gate and Regression Check (Rc) enforcement in `repo promote`.
- Automated state synchronization added to `tasks move` (syncs pipeline code back to feature branch).
- Automated git checkout to feature branch on demotion.
- All pipeline stages now correctly enforce state requirements (`REVIEW` status + `Rc` flag).

## Findings
- Initial pipeline automation in `repo.py` lacked visibility into the `tasks` state machine.
- Branch synchronization requires explicit branch checking and `git checkout` after automated merges.

## Mitigations
- Added explicit state-machine gate logic in `repo.py`.
- Unified the `tasks move` demotion flow with Git sync and metadata resets.

## Next Steps
- Final verification of task 80.
- Archive task 80.