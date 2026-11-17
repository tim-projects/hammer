Test additions (in the new repo these land with Task 14's test plan; in tasks-ai they prove
task 463's fix before it merges):
1. Net-growth test: count `/tmp/hammer_*` dirs before and after running one test file (subprocess
   pytest on a small file) and assert zero net growth. Put it in `tests/` as its own test module.
2. Loud-failure test: monkeypatch `shutil.rmtree` to raise inside the harness tearDown path and
   assert the test FAILS (proves the ignore_errors removal is real).
3. addCleanup test: raise in setUp after the mkdtemp calls and assert the dirs are still removed.
4. Fixture note: prefer `tmp_path` over `tempfile.mkdtemp` in `tests/hammer_test_base.py:52-53`
   if it keeps automatic reclamation — only if it does not break HAMMER_DEV_TASKS_DIR semantics.
