# Agent Task Management Protocol

AI Agents should follow these instructions to manage their workflow using the `tasks-ai` CLI.

## ⚠️ Important: Use Local tasks-ai

This repo has a local `tasks.py` that should be used instead of the system-installed `tasks-ai` binary. The local version may be newer or have modifications.

```bash
# Use this repo's version (recommended)
python tasks.py -j list
```

## 🤖 Discovery & Protocol

Run `python tasks.py --help` to discover the interface, JSON schemas, and operational rules.

## 🤖 Mandatory Workflow

1. **Discovery**: On every session start, run `python tasks.py -j list` to identify high-priority work.
2. **Initialization**: If `tasks-ai` is not initialized, run `python tasks.py init`.
3. **Activation**: Before writing any code, move your target task to PROGRESSING using its numeric Id:
   ```bash
   python tasks.py -j move <id> PROGRESSING
   ```
4. **Implementation**: 
   - Perform work on the branch specified in the task metadata.
   - Log all technical findings, debt, or blockers in `.tasks/progressing/<task_id>/current-task.md`.
   - Use `python tasks.py -j checkpoint` frequently to sync your `current-task.md` notes and git commits into the main task record.
5. **Verification**: Once work is complete and tests pass, move to testing:
   ```bash
   python tasks.py -j move <id> TESTING
   ```
6. **Promotion**: Follow the state machine (`TESTING` -> `REVIEW` -> `STAGING` -> `LIVE`).
   - Note: Tasks can move from `REVIEW`, `ARCHIVED`, or `REJECTED` back to `PROGRESSING` if further work is required.
7. **Archiving**: When ready to archive from STAGING:
   - Branch must be merged to main first
   - Run `python tasks.py move <id> ARCHIVED` - if merged, it will prompt for `-y` confirmation
   - Use `python tasks.py move <id> ARCHIVED -y` to auto-push branch to remote and delete local copy
   - Alternatively, move to `REJECTED` if code was not merged

## ⚠️ Operational Rules

- **Always use `-j`**: Never run commands without the `-j` flag for machine-parseable JSON output.
- **No Invisible Work**: Do not modify files unless a task is in the `PROGRESSING` state.
- **Priority First**: Always pick the task with the lowest `P` (Priority) value first.
- **Blockers**: If stuck, move the task to `BLOCKED` immediately and document the reason in `current-task.md` before checkpointing.
- **Dependencies**: Use `python tasks.py -j link <task-id> <blocker-id>` to link a task to a blocker.

## 🔑 Task References

- **Use Numeric Ids**: All commands accept the numeric task Id (e.g., `17`) instead of the filename. Run `python tasks.py list` to see Ids.
- **Multi-Step Moves**: Push a task through multiple states in ONE command:
  ```bash
  python tasks.py -j move <id> READY,PROGRESSING,TESTING
  ```

## 📋 Useful Commands

| Command | Description |
|---------|-------------|
| `python tasks.py list` | List all tasks with Id, Priority, Summary, Type, Branch |
| `python tasks.py show <id>` | Show full task details |
| `python tasks.py show <id> story` | Show only the story section |
| `python tasks.py show <id> tech` | Show only the technical section |
| `python tasks.py show <id> criteria` | Show only the criteria section |
| `python tasks.py show <id> plan` | Show only the plan section |
| `python tasks.py show <id> repro` | Show only the reproduction steps (for issues) |
| `python tasks.py show <id> progress` | Show active progress notes |
| `python tasks.py move <id> <state>` | Move task to new state (use comma-separated for multi-step) |
| `python tasks.py move <id> ARCHIVED -y` | Archive and auto-push/delete branch (requires branch merged to main) |
| `python tasks.py modify <id> --plan "1. Step"` | Update task fields |
| `python tasks.py reconcile <id>` | Archive a task whose branch no longer exists |
| `python repo.py <command>` | Repo management (merge, sync, branch) |
| `python check.py` | Run validation checks (lint, test, typecheck, format) |
| `python check.py all` | Run all validation checks |
| `python check.py lint --fix` | Run linter with auto-fix |