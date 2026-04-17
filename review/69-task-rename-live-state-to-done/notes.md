
Task: 69-task-rename-live-state-to-done

## Progress
- Renamed "LIVE" to "DONE" in codebase.
- Updated `constants.py` and `cli.py` for state machine logic.
- Updated documentation and test suites.
- Validated with `check.py`.

## Findings
- Test suite failures were due to explicit transition restrictions ("BACKLOG -> PROGRESSING" is now invalid, requires READY transition).
- Migration script had logical errors (migrating "done" to "done" instead of "live" to "done").

## Mitigations
- Updated `test_robustness.py` and `test_tasks.py` to use correct state transition sequence ("READY,PROGRESSING").
- Fixed `_migrate_live_to_done` method in `cli.py` to correctly handle migration from "live" to "done".