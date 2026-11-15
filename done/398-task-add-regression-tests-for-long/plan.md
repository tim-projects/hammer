1. Mount the task worktree and confirm f5ce5bcc is present in tasks_ai/utils.py
2. Add the prose cases and the path cases to tests/test_tasks.py, extending or adding a test beside test_long_form_flags_accept_file_path
3. Record the whitespace rule and the spaces limit in the resolve_content docstring
4. Run pytest tests/test_tasks.py -q and confirm only the two pre-existing error-code failures remain
5. Checkpoint findings, then promote TESTING, REVIEW, STAGING, DONE