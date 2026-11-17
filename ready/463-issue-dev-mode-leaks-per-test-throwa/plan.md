1. 1. Trace which path leaks: instrument one test (print the mkdtemp path, ls after tearDown) to
2.    confirm whether the store dir, the `-repo` clone, or both survive, and why
3.    (ignore_errors failure vs. tearDown not reached).
4. 2. Harden `tests/hammer_test_base.py` tearDown (and add addCleanup for the same dirs): remove
5.    ignore_errors, fail loudly on cleanup failure.
6. 3. Consider pytest's `tmp_path` fixture instead of mkdtemp for automatic reclamation.
7. 4. Decide the policy for interrupted runs: either accept (documented) or a bootstrap-time sweep
8.    of stale `hammer_*` harness dirs that no live store references. Do NOT sweep live repos.
9. 5. Add the regression test from the criteria (zero net growth for one file; run-count stable).
10. 6. Re-run the full suite twice back-to-back on a clean /tmp and confirm identical results and
11.    no net growth.