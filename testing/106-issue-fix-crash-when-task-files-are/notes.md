# Progress: Fix crash when task files are corrupted
## Findings
- FM.load crashes when meta.json is corrupted (invalid JSON) or empty.
- TasksCLI._clear_delete_marks in __init__ scans all tasks, making the crash persistent for all commands.
## Fixes applied
1. Updated tasks_ai/file_manager.py:FM.load to catch json.JSONDecodeError and ValueError.
2. Updated tasks_ai/file_manager.py:FM.load to check if path is a directory before os.listdir.
3. Updated tasks_ai/cli.py:_clear_delete_marks to catch all exceptions during task load and log a warning.
