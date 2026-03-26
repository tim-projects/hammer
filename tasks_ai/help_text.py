# Agent Guidance embedded in CLI

AGENT_GUIDANCE = """
TASK REFERENCES: Use the numeric Id (e.g., "17") instead of the filename for all operations. 
Run 'tasks-ai list' to see task Ids alongside titles.

MULTI-STEP MOVES: Push a task through multiple states in ONE command using comma-separated statuses.
Example: 'tasks-ai move 1 READY,PROGRESSING,TESTING' moves from BACKLOG directly to TESTING.

USEFUL COMMANDS:
  tasks-ai list                   List all tasks with Id, Priority, Summary, Type, Branch
  tasks-ai show <id>              Show full task details
  tasks-ai show <id> story        Show only the story section  
  tasks-ai show <id> repro        Show only the reproduction steps (for issues)
  tasks-ai show <id> progress    Show active progress notes
  tasks-ai move <id> <state>      Move task to new state (use comma-separated for multi-step)
  tasks-ai modify <id> --plan "1. Step"  Update task fields
  tasks-ai reconcile all          Archive tasks whose branches no longer exist in remote

STATE MACHINE: BACKLOG -> READY -> PROGRESSING -> TESTING -> REVIEW -> STAGING -> LIVE -> ARCHIVED
"""

MISSION = """Misson: Identify and fix the highest priority test failures first."""


def get_help_text():
    return AGENT_GUIDANCE + "\n" + MISSION
