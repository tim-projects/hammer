---
Task: 469-issue-fix-transition-matrix-for-unif
---

- Progress: Updated tests/test_all_transitions.py so allowed-transition validation blockers are recognized from status=next_step plus next_step/hint, while legacy error-field detection remains supported. Focused test passes (1 passed).
- Findings: Full suite reached 358 passed, 1 skipped, 290 subtests passed with one unrelated dev-init local-clone filesystem race; that failing test passed immediately when rerun alone.
- Mitigations: No production behavior changed. Unified blockers require status=next_step and validation wording, so unrelated next-step responses and transition assertions are not weakened.
