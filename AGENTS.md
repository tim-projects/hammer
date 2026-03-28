# Agent Task Management Protocol

AI Agents should follow these instructions to manage their workflow using the `tasks-ai` CLI.

## 🤖 Discovery & Protocol

Run `tasks-ai --help` to discover the interface, JSON schemas, and operational rules.

## 🤖 Mandatory Workflow

1. **Discovery**: On every session start, run `tasks-ai -j list` to identify high-priority work.
2. **Initialization**: If `tasks-ai` is not initialized, run `tasks-ai init`.
3. **Activation**: Before writing any code, move your target task to PROGRESSING using its numeric Id:
   ```bash
   tasks-ai -j move <id> PROGRESSING
   ```
4. **Implementation**: 
   - Perform work on the branch specified in the task metadata.
   - Log all technical findings, debt, or blockers in `.tasks/progressing/<task_id>/current-task.md`.
   - Use `tasks-ai -j checkpoint` frequently to sync your `current-task.md` notes and git commits into the main task record.
5. **Verification**: Once work is complete and tests pass, move to testing:
   ```bash
   tasks-ai -j move <id> TESTING
   ```
6. **Promotion**: Follow the state machine (`TESTING` -> `REVIEW` -> `STAGING` -> `LIVE`).
   - Note: Tasks can move from `REVIEW`, `ARCHIVED`, or `REJECTED` back to `PROGRESSING` if further work is required.
7. **Archiving**: When ready to archive from STAGING:
   - Branch must be merged to main first
   - Run `tasks-ai move <id> ARCHIVED` - if merged, it will prompt for `-y` confirmation
   - Use `tasks-ai move <id> ARCHIVED -y` to auto-push branch to remote and delete local copy
   - Alternatively, move to `REJECTED` if code was not merged

## ⚠️ Operational Rules

- **Always use `-j`**: Never run commands without the `-j` flag for machine-parseable JSON output.
- **No Invisible Work**: Do not modify files unless a task is in the `PROGRESSING` state.
- **Priority First**: Always pick the task with the lowest `P` (Priority) value first.
- **Blockers**: If stuck, move the task to `BLOCKED` immediately and document the reason in `current-task.md` before checkpointing.
- **Dependencies**: Use `tasks-ai -j link <task-id> <blocker-id>` to link a task to a blocker.

## 🔑 Task References

- **Use Numeric Ids**: All commands accept the numeric task Id (e.g., `17`) instead of the filename. Run `tasks-ai list` to see Ids.
- **Multi-Step Moves**: Push a task through multiple states in ONE command:
  ```bash
  tasks-ai -j move <id> READY,PROGRESSING,TESTING
  ```

## 📋 Useful Commands

| Command | Description |
|---------|-------------|
| `tasks-ai list` | List all tasks with Id, Priority, Summary, Type, Branch |
| `tasks-ai show <id>` | Show full task details |
| `tasks-ai show <id> story` | Show only the story section |
| `tasks-ai show <id> tech` | Show only the technical section |
| `tasks-ai show <id> criteria` | Show only the criteria section |
| `tasks-ai show <id> plan` | Show only the plan section |
| `tasks-ai show <id> repro` | Show only the reproduction steps (for issues) |
| `tasks-ai show <id> progress` | Show active progress notes |
| `tasks-ai move <id> <state>` | Move task to new state (use comma-separated for multi-step) |
| `tasks-ai move <id> ARCHIVED -y` | Archive and auto-push/delete branch (requires branch merged to main) |
| `tasks-ai modify <id> --plan "1. Step"` | Update task fields |
| `tasks-ai reconcile <id>` | Archive a task whose branch no longer exists |