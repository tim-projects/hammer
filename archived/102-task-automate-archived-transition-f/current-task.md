---
Task: 102-task-automate-archived-transition-f
---

## Status: COMPLETED ✅

## Changes Made

### tasks_ai/cli.py (lines 1392-1456)
- Added logic to detect when target is ARCHIVED and branch is merged to main
- If branch is merged, auto-set missing flags: Rc, Tp, Vp, Ar
- Skip state machine check for merged branches transitioning to ARCHIVED
- Still enforce checkbox completeness

### tasks_ai/cli.py (lines 660-685) - find_task fix
- **Bug fix**: When searching by numeric ID, prioritize metadata Id match over directory name
- This prevents finding corrupted directories with just numeric names
- Prevents `git checkout <id>` errors when task directory name differs from metadata Id

### tests/tasks_ai/cli.py
- Same fixes applied

## Testing

- All 81 tests pass
- Normal workflow works end-to-end
- Numeric ID lookup now correctly finds task by metadata Id first