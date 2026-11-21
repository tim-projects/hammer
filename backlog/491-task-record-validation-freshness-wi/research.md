RESEARCH (491 - TpBase freshness):
- Verified: ValidationHook (pipeline_hooks.py:133) writes Tp False at :163 and True at :174, and skips rerun when Tp is already true; modify --tests-passed sets the same bool.
- 461 landed 'Synchronize stale task branch before validation' (WorktreeSync area, pipeline_hooks.py:491) - READ IT FIRST: branch sync may already make some staleness cases moot; TpBase complements it by recording which origin/main SHA the checks ran against.
- Plan: store TpBase = origin/<default> sha written in the same commit/transaction as Tp so they can never disagree; gate compares TpBase to the current origin sha and reruns when stale.
- Keep Tp a bool: TestingToReviewGateHook (:244) and modify --tests-passed depend on the type.
