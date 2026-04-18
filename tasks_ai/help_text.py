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
  tasks move <id> <state>      Move task to new state (use comma-separated for multi-step)
  tasks move <id> ARCHIVED -y  Archive and auto-push/delete branch (requires merged to main)
  tasks modify <id> --plan "1. Step"  Update task fields
  tasks modify <id> --regression-check  Mark regression check as passed (enables STAGING)
  tasks reconcile              Scan for tasks with merged branches (dry-run)
  tasks reconcile --all        Clean up merged branches and archive tasks
  tasks cleanup --dry-run      Preview what would be cleaned up
  tasks cleanup               Clean up merged branches, push to remote, delete local, archive tasks
  tasks doctor [--fix]         Diagnose repository health; auto-fix with --fix flag

STATE MACHINE: BACKLOG -> READY -> PROGRESSING -> TESTING -> REVIEW -> STAGING -> DONE -> ARCHIVED
               (REJECTED also available from TESTING/STAGING)

DOCTOR: Run 'tasks doctor' to diagnose repository health. Detects:
  - Missing state folders
  - Tasks with missing or incomplete metadata
  - Invalid YAML in task files
  - Orphaned git branches (branches without tasks)
  - Stale task counter (counter less than highest task ID + 1)
  - State folder mismatches (task's St field doesn't match its folder)
Use 'tasks doctor --fix' to automatically fix:
  - Create missing state folders
  - Bump stale task counter
  - Move tasks to correct state folders
  - (Other issues generate bug reports for manual review)

REGRESSION CHECK: Moving to REVIEW auto-generates:
  - .tasks/review/<id>/diff.patch - Full diff
  - .tasks/review/<id>/diff.summary - Condensed view with file headers and line counts

You MUST review EACH FILE before passing regression check:
  1. Run 'tasks show <id> review' to see changed files summary
  2. Run 'tasks review <id> ' to confirm each file (e.g., tasks review 83 repo.py)
  3. Run 'tasks review --list' to see review progress
  4. Once ALL files reviewed, run 'tasks modify <id> --regression-check' to enable STAGING

The review progress is tracked in the task metadata (Rv field). Moving to REVIEW or 
clearing Rc also clears the review progress.
"""

MISSION = """Mission: Identify and fix the highest priority test failures first."""


def get_help_text():
    return AGENT_GUIDANCE + "\n" + MISSION
