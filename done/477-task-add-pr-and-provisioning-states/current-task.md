---
Task: 477-task-add-pr-and-provisioning-states
---

- Progress: Implemented PR and PROVISIONING pipeline states, folders, ordered successors, transition tables, and Ap approval metadata. Added focused CLI coverage for legal moves and forbidden skips; transition legality now precedes exit hooks so skipped states consistently return FORBIDDEN_TRANSITION. Validation: ./hammer check all passed (lint, test, typecheck, format); affected suites passed (52 tests, 3 subtests); focused suite passed (3 tests, 3 subtests).
- Findings: 
- Mitigations: 
