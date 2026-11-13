
- Progress: Docs updated on branch 384-task-document-file-path-submission.
- Findings: tasks_ai/help_text.py is a single-line source string, so inserted text must avoid apostrophes (single-quoted literal).
- Debt: help_text.py entry is a compact 4-line block in USEFUL COMMANDS; per-flag -h help in tasks.py already carried the convention from task 382.