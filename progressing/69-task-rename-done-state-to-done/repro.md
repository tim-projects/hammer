Verification steps:

1. Run `python check.py all` to ensure all validation passes

2. Verify state constants:
   ```bash
   grep -n "LIVE" tasks_ai/constants.py  # Should return no results
   grep -n "DONE" tasks_ai/constants.py  # Should show new DONE state
   ```

3. Verify CLI works:
   ```bash
   python tasks.py list  # Should show states without LIVE
   ```

4. Verify backward migration:
   - Create test .tasks/live folder
   - Run tasks command
   - Should auto-migrate to .tasks/done

5. Verify tasks doctor:
   ```bash
   python tasks.py doctor --migrate-live  # Should work
   ```

6. Verify tests pass:
   ```bash
   python -m pytest test_tasks.py -v
   python -m pytest test_robustness.py -v
   ```