1. ```
2. cd ~/git/tasks-ai
3. b=$(ls -d /tmp/hammer_tasks_* /tmp/hammer_test_* /tmp/hammer_remote_* 2>/dev/null | wc -l)
4. python3 -m pytest tests/test_init_backup.py -q          # 2 passed, green
5. a=$(ls -d /tmp/hammer_tasks_* /tmp/hammer_test_* /tmp/hammer_remote_* 2>/dev/null | wc -l)
6. echo "leftovers before=$b after=$a"                      # observed: 139 -> 141 (leak on green run)
7. df -h /tmp | tail -1
8. ```
9. Full-suite poisoning (for reference, ~37 min, needs a clean /tmp first):
10. ```
11. rm -rf /tmp/hammer_tasks_*-repo /tmp/hammer_tasks_???????? /tmp/hammer_test_* /tmp/hammer_remote_*
12. cd ~/git/tasks-ai && python3 -m pytest tests/ -q 2>&1 | tail -3
13. # with /tmp full beforehand the same command ends: 173 failed, 180 passed (OSError Errno 28)
14. ```