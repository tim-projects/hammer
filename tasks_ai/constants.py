# tasks_ai/constants.py

TASKS_DIR = ".tasks"
TASKS_BRANCH = "tasks"
CURRENT_TASK_FILENAME = "current-task.md"

STATE_FOLDERS = {
    "BACKLOG": "backlog",
    "READY": "ready",
    "PROGRESSING": "progressing",
    "BLOCKED": "blocked",
    "TESTING": "testing",
    "REVIEW": "review",
    "STAGING": "staging",
    "LIVE": "live",
    "ARCHIVED": "archived",
    "REJECTED": "rejected",
}

ALLOWED_TRANSITIONS = {
    "BACKLOG": ["READY", "PROGRESSING"],
    "READY": ["PROGRESSING", "BLOCKED"],
    "PROGRESSING": ["TESTING", "BLOCKED"],
    "TESTING": ["REVIEW", "BLOCKED", "REJECTED"],
    "REVIEW": ["STAGING", "TESTING", "BLOCKED", "PROGRESSING"],
    "STAGING": ["LIVE", "ARCHIVED", "REVIEW", "BLOCKED", "REJECTED"],
    "LIVE": ["ARCHIVED", "STAGING", "BLOCKED"],
    "BLOCKED": ["READY", "PROGRESSING", "TESTING", "REVIEW", "STAGING", "LIVE"],
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
}

AGENT_GUIDANCE = """
AGENT OPERATIONAL PROTOCOL:
0. HELP: Always use -j for JSON output. Use tasks-ai <command> -h for any subcommand.
1. OUTPUT: Always use -j flag for machine-parseable JSON. 
   Schema: {"success": bool, "error": str|null, "messages": [str], "data": {}}
2. TASK REFERENCES: Use the numeric Id (e.g., "1") instead of the filename for all operations. 
   Run 'list' to see task Ids alongside titles.
3. MULTI-STEP MOVES: Push a task through multiple states in ONE command using comma-separated statuses.
   Example: 'tasks-ai move 1 READY,PROGRESSING,TESTING' moves from BACKLOG directly to TESTING.
   This bypasses the need for 3 separate move commands.
4. CREATION: 'create' requires --story, --tech, --criteria, and --plan. 
   --repro is mandatory for --type issue. Titles must be >= 10 chars.
5. LIFECYCLE: BACKLOG -> READY -> PROGRESSING -> TESTING -> REVIEW -> STAGING -> LIVE -> ARCHIVED.
   - Note: REVIEW, ARCHIVED, and REJECTED tasks can move back to PROGRESSING if needed.
   - Task MUST be in PROGRESSING before modifying project code.
   - 'move' to PROGRESSING creates/syncs '.tasks/progressing/<task_id>/current-task.md'.
6. PROGRESS: Use 'modify' to update --progress, --findings, or --mitigations.
   - Updates to the active task automatically sync to its 'current-task.md'.
   - Use '.tasks/progressing/<task_id>/current-task.md' as your primary scratchpad while working.
7. SYNC: Use 'checkpoint' to pull git commits and current-task.md notes into the task file.
8. ARCHIVING: When moving STAGING -> ARCHIVED:
   - Branch must be merged to main first
   - Use 'tasks-ai move <id> ARCHIVED' - if merged, it will prompt for -y
   - Use 'tasks-ai move <id> ARCHIVED -y' to auto-push and delete branch
   - Or move to REJECTED if code was not merged
9. RULES: 
   - All blockers (Bl) in metadata MUST be ARCHIVED before moving to PROGRESSING.
   - Use 'list' to find tasks and 'current' to see full metadata/logs.
10. ERROR RECOVERY: If a command fails, read the 'error' field in the JSON response. 
   It will contain specific guidance and allowed next steps (HINT).
"""
