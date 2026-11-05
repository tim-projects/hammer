1. In tasks.py make filename a required positional for current and checkpoint (drop nargs='?'); confirm undo stays required
2. In tasks_ai/task_service.py:76 get_active_task: stop silently returning items[0] when filename is None; return (None, None) so callers surface the error
3. Update commands/checkpoint.py and commands/current.py error path to list PROGRESSING candidates and the expected usage line
4. Add user tests under tests/ for the no-id-with-multiple-PROGRESSING case using --dev
5. Run ./hammer check lint and ./hammer check test