---
Task: 491-task-record-validation-freshness-wi
---

- Progress: Implemented TpBase freshness recording in ValidationHook and added focused regression tests.
- Findings: The memo now records origin/<default> SHA (local default fallback when no remote ref exists). A missing or stale TpBase invalidates Tp and reruns checks; the green write persists Tp=True and TpBase together.
- Mitigations: Focused tests passed (16 tests plus 3 subtests); ./hammer check all passed lint, tests, typecheck, and format.
