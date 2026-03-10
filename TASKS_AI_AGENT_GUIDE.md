# Tasks AI: AI Agent Operational Guide

This guide defines the interface and state machine for the `tasks` system. 

## 1. Interaction Protocol

### Global JSON Mode
All agents MUST use the global `--json` flag for all commands to ensure a stable, parseable stream.
**Command Pattern:** `tasks --json <command> [args]`

---

## 4. File Structure & Metadata

### Mandatory Content Sections
Agents MUST populate these sections upon creation or when moving to `PROGRESSING`:
- **Tasks**: `Requirements`, `Success/Acceptance Criteria`.
- **Issues**: `Reproduction Steps` (must state "Unknown" if not yet identified).

{
  "success": true,
  "messages": ["Contextual logs", "Auto-archiving status"],
  "data": { ... command specific data ... }
}
```
#### Error
```json
{
  "success": false,
  "error": "Error description",
  "messages": ["Logs captured before failure"]
}
```

---

## 2. Command Reference

| Command | Arguments | Description |
| :--- | :--- | :--- |
| `init` | None | Bootstraps the `.tasks` worktree and branch. |
| `list` | `--all` | Returns structured task list. Default excludes `ARCHIVED`. |
| `create` | `title [--type task\|issue] [-p PRIO]` | Generates a new file in `backlog/`. |
| `move` | `filename status` | Updates state, moves file, and checkpoints content. |
| `current` | `[filename]` | Returns active task metadata and `current-task.md` dump. |
| `checkpoint`| `[filename]` | Force-syncs branch commits and dump file to the task. |
| `link` | `filename blocker` | Defines a blocking dependency. |

---

## 3. Workflow State Machine

### Allowed Transitions
Agents MUST NOT attempt to skip stages. The CLI enforces the following:
- `BACKLOG` -> `READY`
- `READY` -> `PROGRESSING` | `BLOCKED`
- `PROGRESSING` -> `TESTING` | `BLOCKED`
- `TESTING` -> `REVIEW` | `BLOCKED`
- `REVIEW` -> `STAGING` | `TESTING` | `BLOCKED`
- `STAGING` -> `LIVE` | `REVIEW` | `BLOCKED`
- `LIVE` -> `ARCHIVED` | `STAGING` | `BLOCKED`
- `BLOCKED` -> any state between `READY` and `LIVE`.

### Critical Constraints
1. **Concurrency**: Only ONE task/issue may be in `PROGRESSING` at any time.
2. **Blockers**: A task cannot move to `PROGRESSING` unless all tasks in its `BlockedBy` (Bl) list are `ARCHIVED`.
3. **Archival**: Moving to `ARCHIVED` requires at least one commit found on the feature branch.
4. **Auto-Archive**: The CLI automatically archives `LIVE` tasks older than 7 days on every run.

---

## 4. File Structure & Metadata

### Filenames
Format: `{type}_{branch-slug}.md`
- **Type**: `task` or `issue`
- **Branch**: The git branch associated with this work.

### Metadata Keys (Frontmatter)
Files use optimized short-keys to save character space:
- `Ti`: Title
- `St`: State (Current folder name)
- `Cr`: Created timestamp (yymmdd HH:MM)
- `Bl`: List of blocking filenames
- `Pr`: Priority (1=Highest, 9=Lowest)

### Auxiliary Files
- **Logs**: `tasks/logs/{filename}` tracks every transition.
- **Dump**: `tasks/current-task.md` is the scratchpad for the active task. Content here is merged into the main file during `move` or `checkpoint`.

---

## 5. Agent Implementation Pattern

1. **Scan**: Run `python3 tasks.py --json list` to find high-priority tasks in `READY`.
2. **Activate**: Run `python3 tasks.py --json move <file> PROGRESSING`.
3. **Work**:
   - Check out the branch named in the task.
   - Perform implementation.
   - Update `tasks/current-task.md` with findings/notes.
   - Commit code changes.
4. **Sync**: Run `python3 tasks.py --json checkpoint` to merge notes and commits into the record.
5. **Verify**: Run `python3 tasks.py --json move <file> TESTING`.
6. **Cycle**: Repeat through `REVIEW`, `STAGING`, and `LIVE`.
