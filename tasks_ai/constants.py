# tasks_ai/constants.py

TASKS_DIR = ".tasks"
TASKS_BRANCH = "tasks"
CURRENT_TASK_FILENAME = "current-task.md"

STATE_FOLDERS = {
    "BACKLOG": "backlog",
    "READY": "ready",
    "PROGRESSING": "progressing",
    "TESTING": "testing",
    "REVIEW": "review",
    "STAGING": "staging",
    "DONE": "done",
    "ARCHIVED": "archived",
    "REJECTED": "rejected",
}

ALLOWED_TRANSITIONS = {
    "BACKLOG": ["READY"],
    "READY": ["PROGRESSING"],
    "PROGRESSING": ["TESTING", "BLOCKED", "REJECTED"],
    "TESTING": ["REVIEW", "BLOCKED", "REJECTED", "PROGRESSING", "STAGING"],
    "REVIEW": ["STAGING", "TESTING", "BLOCKED", "PROGRESSING"],
    "STAGING": ["DONE", "ARCHIVED", "REVIEW", "BLOCKED", "REJECTED", "PROGRESSING"],
    "DONE": ["ARCHIVED", "STAGING", "TESTING", "BLOCKED"],
    "BLOCKED": ["READY", "PROGRESSING", "TESTING", "REVIEW", "STAGING", "DONE"],
    "ARCHIVED": ["PROGRESSING"],
    "REJECTED": ["PROGRESSING"],
}

KEY_MAP = {
    "Id": "Id",
    "Ti": "Title",
    "St": "State",
    "Cr": "Created",
    "Bl": "BlockedBy",
    "Pr": "Priority",
    "Ar": "ArchivedAt",
    "Tp": "TestsPassed",
    "Rc": "RegressionCheck",
}

ALLOWED_CONFIG_KEYS = {
    "story",
    "tech",
    "criteria",
    "plan",
    "tasks_dir",
    "repo.lint",
    "repo.test",
    "repo.type_check",
    "repo.format",
    "repo.skip_user_test_prompt",
}

AGENT_GUIDANCE = """
AGENT OPERATIONAL PROTOCOL:
0. HELP: Always use -j for JSON output. Use tasks <command> -h for any subcommand.
1. OUTPUT: Always use -j flag for machine-parseable JSON. 
   Schema: {"success": bool, "error": str|null, "messages": [str], "data": {}}
2. TASK REFERENCES: Use the numeric Id (e.g., "1") instead of the filename for all operations. 
   Run 'list' to see task Ids alongside titles.
3. MULTI-STEP MOVES: Push a task through multiple states in ONE command using comma-separated statuses.
   Example: 'tasks move 1 READY,PROGRESSING,TESTING' moves from BACKLOG directly to TESTING.
   This bypasses the need for 3 separate move commands.
4. CREATION: 'create' requires --story, --tech, --criteria, and --plan. 
   --repro is mandatory for --type issue. Titles must be >= 10 chars.
 6. REVIEW: When moving to REVIEW, a diff is auto-generated at `.tasks/review/<task_id>/diff.patch`.
    - Review the diff for regressions. If regressions found, move task back to PROGRESSING/TESTING to fix.
    - Once clean, run `tasks modify <id> --regression-check` to mark as passed.
    - Cannot move to STAGING until regression check is passed (Rc metadata set).
 7. PROGRESS: Use 'modify' to update --progress, --findings, or --mitigations.
    - Updates to the active task automatically sync to its 'current-task.md'.
    - Use '.tasks/progressing/<task_id>/current-task.md' as your primary scratchpad while working.
 8. SYNC: Use 'checkpoint' to pull git commits and current-task.md notes into the task file.
 9. ARCHIVING: When moving STAGING -> ARCHIVED:
    - Branch must be merged to main first
    - Use 'tasks move <id> ARCHIVED' - if merged, it will prompt for -y
    - Use 'tasks move <id> ARCHIVED -y' to auto-push and delete branch
    - Or move to REJECTED if code was not merged
 10. RULES: 
    - All blockers (Bl) in metadata MUST be ARCHIVED before moving to PROGRESSING.
    - Use 'list' to find tasks and 'current' to see full metadata/logs.
 11. ERROR RECOVERY: If a command fails, read the 'error' field in the JSON response. 
    It will contain specific guidance and allowed next steps (HINT).
"""
