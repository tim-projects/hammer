# Agent Guidance embedded in CLI

AGENT_GUIDANCE = """
IMPORTANT: Always use -j for JSON output (machine-parseable for agents).
For help on any command, use tasks <command> -h

Pipeline Commands:
  audit <id>        - Generate cryptographic SHA256 hash of the patch file.
                      Required gate: TESTING -> REVIEW.
  verify <id> --proof "..."
                    - Validate criteria and bind proof to a SHA256 audit hash.
                      Required gate: REVIEW -> STAGING.
  reconcile --all   - Auto-sync pipeline state with Git main branch merges.

TASK REFERENCES: Use the numeric Id (e.g., "17") instead of the filename for all operations. 
Run 'tasks list' to see task Ids alongside titles.

MULTI-STEP MOVES: Push a task through multiple states in ONE command using comma-separated statuses.
Example: 'tasks move 1 READY,PROGRESSING,TESTING' moves from BACKLOG directly to TESTING.

USEFUL COMMANDS:
  tasks list                   List all tasks with Id, Priority, Summary, Type, Branch
  tasks show <id>              Show full task details
  tasks move <id> <state>      Move task to new state (use comma-separated for multi-step)
  tasks modify <id> --regression-check  Mark regression check as passed (enables STAGING)
  tasks reconcile --all        Clean up merged branches and archive tasks
  tasks cleanup                Clean up merged branches, push to remote, delete local, archive tasks
  tasks doctor [--fix]         Diagnose repository health

STATE MACHINE: BACKLOG -> READY -> PROGRESSING -> TESTING -> REVIEW -> STAGING -> DONE -> ARCHIVED

MISSION: Identify and fix the highest priority test failures first.
"""

def get_help_text():
    return AGENT_GUIDANCE
