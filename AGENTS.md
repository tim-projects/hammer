| `hammer check lint --fix` | Run linter with auto-fix |

## ⚠️ Error Handling

<<<<<<< HEAD
When using any tool (`tasks.py`, `repo.py`, `check.py`) and it errors or fails:
1. **STOP immediately** - Do not continue with further commands
2. **Report the error** - Tell the user what happened and the error message
3. **Wait for instruction** - Do not try to fix or work around the error without asking
=======
## ⚠️ Important: Use Local tasks

This repo has a local `tasks.py` that should be used instead of the system-installed `tasks` binary. The local version may be newer or has modifications.

```bash
# Use this repo's version (recommended)
hammer tasks -j list
```

### 🛠️ Development & Testing

When testing the tool itself or performing "dry runs" of task operations without affecting the project's real `.tasks` worktree, use the `--dev` flag. This will use `/tmp/.tasks` as an isolated storage directory. Note that the `--dev` flag is strictly for testing tool behavior and operational workflows in an isolated environment; it should NOT be used to create tasks meant for real project progress.

```bash
# Reset dev environment (if corrupted or needs fresh start)
./scripts/reset-dev.sh

# Initialize dev environment
hammer tasks --dev init

# Run any command in dev mode
hammer tasks --dev list
```

## 🤖 Discovery & Protocol

Run `hammer tasks --help` to discover the interface, JSON schemas, and operational rules.

## 🤖 Mandatory Workflow

1. **Discovery**: On every session start, run `hammer tasks -j list` to identify high-priority work.
2. **Initialization**: If `tasks` is not initialized, run `hammer tasks init`.
3. **Activation**: Before writing any code, move your target task to PROGRESSING using its numeric Id:
   ```bash
   hammer tasks -j move <id> PROGRESSING
   ```
4. **Implementation**: 
   - Perform work on the branch specified in the task metadata.
   - Log all technical findings, debt, or blockers in `.tasks/progressing/<task_id>/current-task.md`.
   - Use `hammer tasks -j checkpoint` frequently to sync your `current-task.md` notes and git commits into the main task record.
5. **Verification**: Once work is complete and tests pass, move to testing:
   ```bash
   hammer tasks -j move <id> TESTING
   ```
6. **Promotion**: Follow the state machine (`TESTING` -> `REVIEW` -> `STAGING` -> `DONE`).
   - When moving to REVIEW, a diff file is auto-generated at `.tasks/review/<task_id>/diff.patch`.
   - **Review the diff for regressions**. If regressions found, move task back to `PROGRESSING` or `TESTING` to fix before proceeding.
   - Once the diff is clean, run `tasks modify <id> --regression-check` to confirm.
   - Note: Tasks can move from `REVIEW`, `ARCHIVED`, or `REJECTED` back to `PROGRESSING` if further work is required.
7. **Archiving**: When ready to archive from STAGING:
   - Branch must be merged to main first
   - Run `hammer tasks move <id> ARCHIVED` - if merged, it will prompt for `-y` confirmation
   - Use `hammer tasks move <id> ARCHIVED -y` to auto-push branch to remote and delete local copy
   - Alternatively, move to `REJECTED` if code was not merged

## ⚠️ Operational Rules

- **Use `repo.py` for all merges**: You MUST use the `hammer repo promote` or `hammer repo merge` commands for all pipeline transitions. Manual Git merges are forbidden.
- **Resolve Validation Errors**: All validation errors (lint, test, typecheck) related to your changes MUST be resolved before promotion.
- **Unrelated Errors**: If validation fails due to pre-existing errors unrelated to your task, you MUST create a new task to address them before merging to `main`. Do not bypass errors.
- **Use `--dev` for testing**: You MUST use the `--dev` flag for all tool experimentation, "dry runs", or any task operation that is not directly part of the active project's workflow. This protects the real `.tasks` worktree.
- **Priority First**: Always pick the task with the lowest `P` (Priority) value first.
- **Blockers**: If stuck, move the task to `BLOCKED` immediately and document the reason in `current-task.md` before checkpointing.
- **Dependencies**: Use `hammer tasks -j link <task-id> <blocker-id>` to link a task to a blocker.
>>>>>>> 19-task-atomic-file-operations

## 🔑 Task References

- **Use Numeric Ids**: All commands accept the numeric task Id (e.g., `17`) instead of the filename. Run `hammer tasks list` to see Ids.
<<<<<<< HEAD
- **Show Task Details**: Show full task details with `hammer tasks show <id>`
- **Show Only Specific Sections**: Use `hammer tasks show <id> story|tech|criteria|plan|progress|repro`
- **Use `--dev` for testing**: Always use `--dev` flag when testing or doing dry runs
=======
- **Multi-Step Moves**: Push a task through multiple states in ONE command:
  ```bash
  hammer tasks -j move <id> READY,PROGRESSING,TESTING
  ```

## 📋 Useful Commands

| Command | Description |
|---------|-------------|
| `hammer tasks list` | List all tasks with Id, Priority, Summary, Type, Branch |
| `hammer tasks show <id>` | Show full task details |
| `hammer tasks show <id> story` | Show only the story section |
| `hammer tasks show <id> tech` | Show only the technical section |
| `hammer tasks show <id> criteria` | Show only the criteria section |
| `hammer tasks show <id> plan` | Show only the plan section |
| `hammer tasks show <id> repro` | Show only the reproduction steps (for issues) |
| `hammer tasks show <id> progress` | Show active progress notes |
| `./scripts/reset-dev.sh` | Reset dev environment (clear /tmp/.tasks) |
| `hammer tasks --dev init` | Initialize isolated dev environment |
| `hammer tasks --dev <cmd>` | Run any task command in isolated /tmp/.tasks |
| `hammer tasks move <id> <state>` | Move task to new state (use comma-separated for multi-step) |
| `hammer tasks move <id> ARCHIVED -y` | Archive and auto-push/delete branch (requires branch merged to main) |
| `hammer tasks modify <id> --plan "1. Step"` | Update task fields |
| `hammer tasks reconcile <id>` | Archive a task whose branch no longer exists |
| `hammer repo <command>` | Repo management (merge, sync, branch) |
| `hammer check` | Run validation checks (lint, test, typecheck, format) |
| `hammer check all` | Run all validation checks |
| `hammer check lint --fix` | Run linter with auto-fix |

## 🚫 Never Skip or Bypass

**NEVER** skip or bypass validation to get something to work:
- Do NOT remove checks from `check.py all`
- Do NOT disable lint/typecheck rules  
- Do NOT modify validation config to hide errors
- Do NOT comment out failing tests

If validation fails:
1. **Fix the actual issue** - Not the validation tool
2. **Create a new task** for pre-existing issues  
3. **Ask the user** what to do instead of bypassing
>>>>>>> 19-task-atomic-file-operations
