Rename LIVE state to DONE with backward compatibility for existing .tasks/live folders.

## Files to Update

### Core Python Files
1. **tasks_ai/constants.py** (lines 15, 26-28, 68):
   - Change `STATE_FOLDERS["LIVE"]` to `STATE_FOLDERS["DONE"] = "done"`
   - Update `ALLOWED_TRANSITIONS` entries from "LIVE" to "DONE"
   - Update LIFECYCLE string in comments/docs

2. **tasks_ai/cli.py** (lines 321, 336, 1401, 1496, 1531-1533, 1557-1559, 2130, 2132, 2150):
   - Update all `STATE_FOLDERS["LIVE"]` references to `STATE_FOLDERS["DONE"]`
   - Update all string comparisons from `== "LIVE"` to `== "DONE"`
   - Update string literals like `"->LIVE"` to `"->DONE"`

3. **tasks_ai/help_text.py** (line 27):
   - Update STATE MACHINE string

### Documentation
4. **AGENTS.md** (line 53): Update promotion workflow reference
5. **README.md** (lines 41, 51, 89): Update state machine diagram and move command

### Tests
6. **test_tasks.py** (lines 127, 158, 173, 182, 184, 193, 195, 247, 262, 277, 286, 287, 296, 298, 307):
   - Update all "LIVE" references to "DONE"

7. **test_robustness.py** (lines 220, 233, 293, 424, 443, 663, 825, 1017, 1137):
   - Update all "LIVE" references to "DONE"

### Scripts/Tools
8. **repo.py** (line 324): Update help text

## Backward Compatibility Strategy

**Chosen Approach: Option A + C (Auto-detection with temporary dual support)**

Implemente auto-detection in `TasksCLI.__init__` or `find_project_root`:
1. Check if `.tasks/done/` exists - use it if present
2. If `.tasks/done/` missing but `.tasks/live/` exists - migrate (rename) on first use
3. Provide deprecation warning for old `.tasks/live/` folder until migration complete

Also implement in `tasks doctor`:
- Add `--migrate-live` flag for explicit migration
- Auto-upgrade checks on initialization

Migration logic:
```python
# In find_project_root or TasksCLI.__init__
live_path = os.path.join(tasks_path, "live")
done_path = os.path.join(tasks_path, "done")

if os.path.exists(live_path) and not os.path.exists(done_path):
    # Migrate live -> done silently on first use
    os.rename(live_path, done_path)
    # Optionally log/mark as migrated
```

## Branch Naming
Branch: `69-task-rename-live-state-to-done` (consistent with task Id)

## Risks and Mitigations

1. **Old .tasks worktree**: Auto-migration will handle - no manual intervention needed
2. **Git history**: No impact - folders renamed, commits unchanged
3. **Corrupted tasks**: Migration skips if done folder already exists (failsafe)
4. **Manual edits**: User can run `tasks doctor --migrate-live` for explicit migration