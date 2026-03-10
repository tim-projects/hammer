# Agent Task Management Protocol

AI Agents should follow these instructions to manage their workflow using the `tasks` CLI.

## 🤖 Mandatory Workflow

1. **Discovery**: On every session start, run `tasks --json list` to identify high-priority work.
2. **Initialization**: If `tasks` is not initialized, run `tasks --json init`.
3. **Activation**: Before writing any code, move your target task to progressing:
   ```bash
   tasks --json move <filename> PROGRESSING
   ```
4. **Implementation**: 
   - Perform work on the branch specified in the task metadata.
   - Log all technical findings, debt, or blockers in `tasks/current-task.md`.
   - Use `tasks --json checkpoint` frequently to sync your `current-task.md` notes and git commits into the main task record.
5. **Verification**: Once work is complete and tests pass, move to testing:
   ```bash
   tasks --json move <filename> TESTING
   ```
6. **Promotion**: Follow the state machine (`TESTING` -> `REVIEW` -> `STAGING` -> `LIVE`) as criteria are met.

## ⚠️ Operational Rules

- **Always use `--json`**: Never run commands without the `--json` flag to ensure parseable output.
- **No Invisible Work**: Do not modify files unless a task is in the `PROGRESSING` state.
- **Priority First**: Always pick the task with the lowest `P` (Priority) value first.
- **Blockers**: If stuck, move the task to `BLOCKED` immediately and document the reason in `current-task.md` before checkpointing.
- **Dependencies**: Use `tasks --json link <task> <blocker>` if you identify a new dependency.
