# Agent Guidance embedded in CLI

AGENT_GUIDANCE = """
IMPORTANT: Always use -j for JSON output (machine-parseable for agents).
For help on any command, use hammer tasks <command> -h

TASK REFERENCES: Use the numeric Id (e.g., "17") instead of the filename for all operations. 
Run 'hammer tasks list' to see task Ids alongside titles.

MULTI-STEP MOVES: Push a task through multiple states in ONE command using comma-separated statuses.
Example: 'hammer tasks move 1 READY,PROGRESSING,TESTING' moves from BACKLOG directly to TESTING.

USEFUL COMMANDS:
  hammer tasks list                   List all hammer tasks with Id, Priority, Summary, Type, Branch
  hammer tasks show <id>              Show full task details
  hammer tasks show <id> story        Show only the story section  
  hammer tasks show <id> repro        Show only the reproduction steps (for issues)
  hammer tasks move <id> <state>      Move task to new state (use comma-separated for multi-step)
  hammer tasks move <id> ARCHIVED -y  Archive and auto-push/delete branch (requires merged to main)
  hammer tasks modify <id> --plan "1. Step"  Update task fields
  hammer tasks modify <id> --regression-check  Mark regression check as passed (enables STAGING)
  hammer tasks reconcile              Scan for hammer tasks with merged branches (dry-run)
  hammer tasks reconcile --all        Clean up merged branches and archive hammer tasks
  hammer tasks cleanup --dry-run      Preview what would be cleaned up
  hammer tasks cleanup               Clean up merged branches, push to remote, delete local, archive hammer tasks
  hammer tasks doctor [--fix]         Diagnose repository health; auto-fix with --fix flag

STATE MACHINE: BACKLOG -> READY -> PROGRESSING -> TESTING -> REVIEW -> STAGING -> DONE -> ARCHIVED
               (REJECTED also available from TESTING/STAGING)

DOCTOR: Run 'hammer tasks doctor' to diagnose repository health. Detects:
  - Missing state folders
  - Tasks with missing or incomplete metadata
  - Invalid YAML in task files
  - Orphaned git branches (branches without hammer tasks)
  - Stale task counter (counter less than highest task ID + 1)
  - State folder mismatches (task's St field doesn't match its folder)
Use 'hammer tasks doctor --fix' to automatically fix:
  - Create missing state folders
  - Bump stale task counter
  - Move hammer tasks to correct state folders
  - (Other issues generate bug reports for manual review)

REGRESSION CHECK: Moving to REVIEW auto-generates a diff at .hammer tasks/review/<id>/diff.patch.
Review the diff carefully. If regressions found, move the task back to PROGRESSING or TESTING to fix.
Once clean, run 'hammer tasks modify <id> --regression-check' to confirm and enable STAGING.
"""

MISSION = """Mission: Identify and fix the highest priority test failures first."""


def get_help_text():
    return AGENT_GUIDANCE + "\n" + MISSION
