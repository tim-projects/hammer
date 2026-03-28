# Agent Guidance embedded in CLI

AGENT_GUIDANCE = """
IMPORTANT: Always use -j for JSON output (machine-parseable for agents).
For help on any command, use tasks-ai <command> -h

TASK REFERENCES: Use the numeric Id (e.g., "17") instead of the filename for all operations. 
Run 'tasks-ai list' to see task Ids alongside titles.

MULTI-STEP MOVES: Push a task through multiple states in ONE command using comma-separated statuses.
Example: 'tasks-ai move 1 READY,PROGRESSING,TESTING' moves from BACKLOG directly to TESTING.

USEFUL COMMANDS:
  tasks-ai list                   List all tasks with Id, Priority, Summary, Type, Branch
  tasks-ai show <id>              Show full task details
  tasks-ai show <id> story        Show only the story section  
  tasks-ai show <id> repro        Show only the reproduction steps (for issues)
  tasks-ai show <id> progress     Show active progress notes
  tasks-ai move <id> <state>      Move task to new state (use comma-separated for multi-step)
  tasks-ai move <id> ARCHIVED -y  Archive and auto-push/delete branch (requires merged to main)
  tasks-ai modify <id> --plan "1. Step"  Update task fields
  tasks-ai reconcile              Scan for tasks with merged branches (dry-run)
  tasks-ai reconcile --all        Clean up merged branches and archive tasks
  tasks-ai cleanup --dry-run      Preview what would be cleaned up
  tasks-ai cleanup               Clean up merged branches, push to remote, delete local, archive tasks

STATE MACHINE: BACKLOG -> READY -> PROGRESSING -> TESTING -> REVIEW -> STAGING -> LIVE -> ARCHIVED
               (REJECTED also available from TESTING/STAGING)
"""

MISSION = """Mission: Identify and fix the highest priority test failures first."""


def get_help_text():
    return AGENT_GUIDANCE + "\n" + MISSION
