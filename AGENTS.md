# Agent Task Management Protocol

AI Agents should follow these instructions to manage their workflow using the `tasks` CLI.

## ⚠️ Important: Use Local tasks

This repo has a local `tasks.py` that should be used instead of the system-installed `tasks` binary. The local version may be newer or have modifications.

```bash
# Use this repo's version (recommended)
python tasks.py -j list
```

### 🛠️ Development & Testing

When testing the tool itself or performing "dry runs" of task operations without affecting the project's real `.tasks` worktree, use the `--dev` flag. This will use `/tmp/.tasks` as an isolated storage directory.

```bash
# Initialize dev environment
python tasks.py --dev init

# Run any command in dev mode
python tasks.py --dev create "Test Task" ...
python tasks.py --dev list
```

## 🤖 Discovery & Protocol

Run `python tasks.py --help` to discover the interface, JSON schemas, and operational rules.

## 🤖 Mandatory Workflow

1. **Discovery**: On every session start, run `python tasks.py -j list` to identify high-priority work.
2. **Initialization**: If `tasks` is not initialized, run `python tasks.py init`.
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

- **Use `python repo.py` for all merges**: You MUST use the `python repo.py promote` or `python repo.py merge` commands for all pipeline transitions. Manual Git merges are forbidden.
- **Resolve Validation Errors**: All validation errors (lint, test, typecheck) related to your changes MUST be resolved before promotion.
- **Unrelated Errors**: If validation fails due to pre-existing errors unrelated to your task, you MUST create a new task to address them before merging to `main`. Do not bypass errors.
- **Use `--dev` for testing**: You MUST use the `--dev` flag for all tool experimentation, "dry runs", or any task operation that is not directly part of the active project's workflow. This protects the real `.tasks` worktree.
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
| `python tasks.py --dev init` | Initialize isolated dev environment |
| `python tasks.py --dev <cmd>` | Run any task command in isolated /tmp/.tasks |
| `python tasks.py move <id> <state>` | Move task to new state (use comma-separated for multi-step) |
| `python tasks.py move <id> ARCHIVED -y` | Archive and auto-push/delete branch (requires branch merged to main) |
| `python tasks.py modify <id> --plan "1. Step"` | Update task fields |
| `python tasks.py reconcile <id>` | Archive a task whose branch no longer exists |
| `python repo.py <command>` | Repo management (merge, sync, branch) |
| `python check.py` | Run validation checks (lint, test, typecheck, format) |
| `python check.py all` | Run all validation checks |
| `python check.py lint --fix` | Run linter with auto-fix |
