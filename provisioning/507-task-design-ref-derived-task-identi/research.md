Findings (2026-11-09, main d8ef45fa) — operator notes in /tmp/t verified in code:
1. create.py:99 and :201 call cli._get_next_id() (TaskCounterProtector.get_next_id, counter.py). derive_task_id(numeric_id,...) only formats <id>-PROGRESSING; it allocates nothing (utils.py).
2. counter.get_next_id takes store_lock (utils.store_lock, kernel flock) for the whole read-increment-write-commit: today's serialization already exists — the counter is a *cache of the high-water*, not a lock.
3. Recovery heuristic _recover_task_counter_from_tasks (cli.py) scans every STATE_FOLDERS folder for the max numeric prefix: the store scan is already the fallback authority.
4. Guard's SQLite refs table is rebuilt from for-each-ref + ls-tree; it is a disposable verifier (plan-guard.md R7 lists ref-based allocation as an open decision, not a chosen one).
5. Automated cleanup (commands/cleanup.py) removes worktrees and merged branches; task records are never deleted — ARCHIVED records persist in .tasks/archived/.
6. Store-lock call sites in cli.py (431/471/1302) are migrations/marks/audit — NOT create. Create's only lock is counter.py's; allocate and record-write are therefore NOT one transaction today.
