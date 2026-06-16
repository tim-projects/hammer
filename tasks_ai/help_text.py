# Agent Guidance embedded in CLI

AGENT_GUIDANCE = """
IMPORTANT: Always use -j for JSON output (machine-parseable for agents).
For help on any command, use tasks <command> -h

### 1. Pipeline Structure
The Pipeline consists of sequential Stages (BACKLOG -> READY -> PROGRESSING -> TESTING -> REVIEW -> STAGING -> DONE -> ARCHIVED).

* Automation Engine: The mechanism that executes the Pipeline.
* Automation Rule: The Automation Engine will chain all Jobs within a Stage automatically.
* Halt Policy: The Pipeline halts only when a Check fails or Manual Intervention (e.g., audit) is required.

Pipeline Commands:
  init              - Construct foundation: Create .tasks directory and configure git.
                      Run this first to initialize workspace storage.
  audit <id>        - Generate cryptographic MD5 hash of the patch file.
                      Required gate: TESTING -> REVIEW.
  verify <id> --proof "..."
                    - Validate criteria and bind proof to a MD5 audit hash.
                      Required gate: REVIEW -> STAGING.
  reconcile --all   - Auto-sync pipeline state with Git main branch merges.

TASK REFERENCES: Use the numeric Id (e.g., "17") instead of the filename for all operations. 
Run 'tasks list' to see task Ids alongside titles.

USEFUL COMMANDS:
  tasks list                   List all tasks with Id, Priority, Summary, Type, Branch
  tasks show <id>              Show full task details
  tasks move <id> <state>      Move task to new state.
  tasks modify <id> --regression-check  Mark regression check as passed (enables STAGING)
  tasks reconcile --all        Clean up merged branches and archive tasks
  tasks cleanup                Clean up merged branches, push to remote, delete local, archive tasks
  tasks doctor [--fix]         Diagnose repository health

STATE MACHINE: BACKLOG -> READY -> PROGRESSING -> TESTING -> REVIEW -> STAGING -> DONE -> ARCHIVED

MISSION: Identify and fix the highest priority test failures first.
"""


def get_help_text():
    return AGENT_GUIDANCE
