1. Replace the four 'init --force' calls with 'init' in tests/test_dev_write_audit.py
2. Delete the stale comment referencing task 356
3. Run tests/test_dev_write_audit.py and tests/test_dev_isolation.py
4. Run ./hammer check all, then move the task through the pipeline
5. Drop the stale --force workaround from the dev write audit