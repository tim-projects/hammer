# 239 Verifiable patch review gate + regression-check hardening

## Findings from investigation (current main)
- modify.py:67-88 `--reviewed` only checks patch `atime >= PatchGenTime` (NOT md5).
- `Reviewed` metadata is WRITE-ONLY: grep shows only modify.py:85 writes it and
  pipeline_hooks.py:20 resets it. No gate reads it.
- modify.py:92-102 `--regression-check` only checks `.tasks/review/<task>.audit`
  EXISTS, then sets Rc='PASSED'. Never calls verify_audit().
- pipeline.py:223-227 `check_audit_integrity` returns True immediately when
  Rc=='PASSED' -> skips verify_audit (md5) + sha256 .audit_hash check.
- pipeline.py:105-109 `audit_integrity` gate body is `pass` (dead).
- tasks.py:65-66 `--reviewed`/`--regression-check` are store_true (default False).
  So every `tasks modify` without the flag hits `else: Rc=''` (wipes Rc) and
  `Reviewed=False`, and `updated=True` always -> extra commit on every modify.
- tests/test_tasks.py:83 `generate_audit` writes `{}` (mock audit). That is why
  `--regression-check` + STAGING tests pass without real hashes.
- tasks create crashed universally: tasks.py:119 passed parent=None to
  create_cmd.run which rejected it. Fixed create.py to accept parent + store Pt.

## Fix plan
1. argparse: default=None for --reviewed/--regression-check.
2. modify --reviewed: write reviews.json per task ([{file, md5, reviewed_at, findings}]);
   require atime>=gen_time (keep) AND record md5 of each patch.
3. modify --regression-check: require Reviewed==True; require audit exists;
   require verify_audit() md5 match; require .audit_hash sha256 integrity (criteria+proof+audit).
   Empty diff -> auto-pass.
4. pipeline.validate_gate: REVIEW->STAGING requires Reviewed+audit_integrity
   (else REGRESSION_CHECK_NOT_PASSED); empty diff auto-pass.
5. check_audit_integrity: remove Rc==PASSED early-return; validate real hashes.
6. Fix test helper generate_audit to produce real audit; add negative tests.

## Notes
- Branch: 239-task-verifiable-patch-review-gate-a (merged main). Auto-commit on progress.
- EPIC/parent (task 86) is half-implemented: constants KEY_MAP has Pt/Ep, DEFAULT_ALLOWED_TRANSITIONS does NOT include EPIC. create now stores Pt. Not enforcing EPIC state transitions (out of scope for this gate work).
