Verification steps:

1. Create a task and move it through READY→PROGRESSING→TESTING→REVIEW:
   ```bash
   python tasks.py create --story "Test" --tech "Tech" --criteria "Criterion" --plan "Plan"
   python tasks.py move <id> READY,PROGRESSING,TESTING,REVIEW
   ```

2. Verify diff file generated:
   ```bash
   ls .tasks/review/<task_id>/diff.patch  # Should exist
   cat .tasks/review/<task_id>/diff.patch  # Should show changes vs main
   ```

3. Verify agent instruction appears in output:
   - Output should mention diff location and `tasks modify --regression-check`

4. Verify gate blocks without Rc:
   ```bash
   python tasks.py move <id> STAGING  # Should fail with hint
   ```

5. Set regression check flag:
   ```bash
   python tasks.py modify <id> --regression-check
   ```

6. Verify STAGING now allowed:
   ```bash
   python tasks.py move <id> STAGING  # Should succeed
   ```

7. Run full test suite:
   ```bash
   python -m pytest test_tasks.py test_robustness.py test_dev_mode.py -v
   python check.py all
   ```
