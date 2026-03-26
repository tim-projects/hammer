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
}

ALLOWED_TRANSITIONS = {
    "BACKLOG": ["READY"],
    "READY": ["PROGRESSING", "BLOCKED"],
    "PROGRESSING": ["TESTING", "BLOCKED"],
    "TESTING": ["REVIEW", "BLOCKED"],
    "REVIEW": ["STAGING", "TESTING", "BLOCKED"],
    "STAGING": ["LIVE", "REVIEW", "BLOCKED"],
    "LIVE": ["ARCHIVED", "STAGING", "BLOCKED"],
    "BLOCKED": ["READY", "PROGRESSING", "TESTING", "REVIEW", "STAGING", "LIVE"],
}

KEY_MAP = {
    "Ti": "Title",
    "St": "State",
    "Cr": "Created",
    "Bl": "BlockedBy",
    "Pr": "Priority",
    "Ar": "ArchivedAt",
}

AGENT_GUIDANCE = """
AGENT OPERATIONAL PROTOCOL:
1. OUTPUT: Always use -j flag for machine-parseable JSON. 
   Schema: {"success": bool, "error": str|null, "messages": [str], "data": {}}
2. CREATION: 'create' requires --story, --tech, --criteria, and --plan. 
   --repro is mandatory for --type issue. Titles must be >= 10 chars.
3. LIFECYCLE: BACKLOG -> READY -> PROGRESSING -> TESTING -> REVIEW -> STAGING -> LIVE -> ARCHIVED.
   - Task MUST be in PROGRESSING before modifying project code.
   - 'move' to PROGRESSING creates/syncs '.tasks/progressing/<task_id>/current-task.md'.
4. PROGRESS: Use 'modify' to update --progress, --findings, or --mitigations.
   - Updates to the active task automatically sync to its 'current-task.md'.
   - Use '.tasks/progressing/<task_id>/current-task.md' as your primary scratchpad while working.
5. SYNC: Use 'checkpoint' to pull git commits and current-task.md notes into the task file.
6. RULES: 
   - All blockers (Bl) in metadata MUST be ARCHIVED before moving to PROGRESSING.
   - Use 'list' to find tasks and 'current' to see full metadata/logs.
7. ERROR RECOVERY: If a command fails, read the 'error' field in the JSON response. 
   It will contain specific guidance and allowed next steps (HINT).
"""
