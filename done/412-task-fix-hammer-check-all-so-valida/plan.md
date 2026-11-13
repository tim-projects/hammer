1. Reproduce first: with the current /bin/true config run ./hammer check lint and confirm it exits 0 with no output
2. Delete the true entries from check.py get_commands and validator.py _get_commands, and the /bin/ normalization at check.py:313-315
3. Make a skip an explicit failure: /bin/true or true yields exit 1 with a message naming repo.<key> and the tasks config detect --save fix
4. Replace the cli.py:798-806 seed block with detection results, writing no key when nothing is detected
5. Backfill .tasks/config.yaml with tasks config detect --save then set repo.format to ruff format, and confirm with tasks config list
6. Update scripts/test-setup.sh and decide the fixture strategy for the 9 test files that seed /bin/true
7. Add tests/test_check_no_skip.py covering the /bin/true config case and the missing-key case
8. Run ./hammer check all, record the real baseline, and file the pre-existing lint and test debt as its own task before promoting this one