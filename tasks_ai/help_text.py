# Agent Guidance embedded in CLI

AGENT_GUIDANCE = """
IMPORTANT: Always use -j for JSON output (machine-parseable for agents).
For help on any command, use tasks <command> -h

TASK REFERENCES: Use the numeric Id (e.g., "17") instead of the filename for all operations. 
Run 'tasks list' to see task Ids alongside titles.

MULTI-STEP MOVES: Push a task through multiple states in ONE command using comma-separated statuses.
Example: 'tasks move 1 READY,PROGRESSING,TESTING' moves from BACKLOG directly to TESTING.

USEFUL COMMANDS:
  tasks list                   List all tasks with Id, Priority, Summary, Type, Branch
  tasks show <id>              Show full task details
  tasks show <id> story        Show only the story section  
  tasks show <id> repro        Show only the reproduction steps (for issues)
  tasks show <id> progress     Show active progress notes
  tasks move <id> <state>      Move task to new state (use comma-separated for multi-step)
  tasks move <id> ARCHIVED -y  Archive and auto-push/delete branch (requires merged to main)
  tasks modify <id> --plan "1. Step"  Update task fields
  tasks modify <id> --regression-check  Mark regression check as passed (enables STAGING)
  tasks reconcile              Scan for tasks with merged branches (dry-run)
  tasks reconcile --all        Clean up merged branches and archive tasks
  tasks cleanup --dry-run      Preview what would be cleaned up
  tasks cleanup               Clean up merged branches, push to remote, delete local, archive tasks

STATE MACHINE: BACKLOG -> READY -> PROGRESSING -> TESTING -> REVIEW -> STAGING -> LIVE -> ARCHIVED
               (REJECTED also available from TESTING/STAGING)
               
REGRESSION CHECK: Moving to REVIEW auto-generates a diff at `.tasks/review/<task_id>/diff.patch`.
Review the diff carefully. If regressions found, move the task back to PROGRESSING or TESTING to fix issues.
Once the diff is clean, run `tasks modify <id> --regression-check` to confirm and enable STAGING.
               
REGRESSION CHECK: Moving to REVIEW auto-generates diff at .tasks/review/<id>/diff.patch.
Review diff carefully. If regressions found, move task back to PROGRESSING/TESTING to fix.
Once clean, run 'tasks modify <id> --regression-check' to enable STAGING.
"""

MISSION = """Mission: Identify and fix the highest priority test failures first."""


def get_help_text():
    return AGENT_GUIDANCE + "\n" + MISSION
