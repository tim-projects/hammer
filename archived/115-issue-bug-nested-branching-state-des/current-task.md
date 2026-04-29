---
Task: 115-issue-bug-nested-branching-state-des
---



- Progress: Implemented fix to create new task branch from default branch (main).
- Findings: Creating nested branches from the current branch causes state fragmentation as .tasks state is branch-dependent.
- Mitigations:
  1. Current: Created new branch from main to break nesting.
  2. Better: Create from main, then merge current active branch into the new branch to preserve progress without nested branch dependency.
- Plan: Modify `create` in `tasks_ai/cli.py` to checkout main, create branch, then merge the original branch before switching to the new branch.