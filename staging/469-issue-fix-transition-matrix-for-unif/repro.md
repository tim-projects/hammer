1. 1. Run `python3 -m pytest tests/test_all_transitions.py -q` on main.
2. 2. Observe the REVIEW to STAGING transition returns `status: next_step` with a regression-check hint.
3. 3. Observe the test reports `Transition REVIEW->STAGING resulted in unexpected state` because it only reads the obsolete `error` field.