# Root Cause Analysis: Task ID/Branch Mismatch Issue

## Primary Cause
The task ID/branch mismatch occurred due to **manual manipulation of task metadata files**. Specifically:

1. Task 178 was created correctly with ID 178 in `.tasks/backlog/178-task-consolidate-repo-merge-and-tas/`
2. The task was subsequently moved to progressing state (correctly preserving ID 178)
3. At some point, someone manually edited the meta.json file in the **backlog directory** (not the active progressing directory)
4. They changed the ID from 178 to 181, likely intending to modify a different task
5. This created an inconsistency where:
   - `.tasks/backlog/178-task-consolidate-repo-merge-and-tas/` contained `{"Id": 181}` (incorrect)
   - `.tasks/progressing/178-task-consolidate-repo-merge-and-tas/` contained correct metadata with `"Id": 178`

## Why This Happened
The hammer system stores task state in the directory location:
- Backlog: `.tasks/backlog/{task-dir}/`
- Progressing: `.tasks/progressing/{task-dir}/`
- etc.

When moving between states, the entire task directory is moved. However, if someone manually edits files in a stale directory (like the backlog copy after the task has been moved), they create inconsistencies.

The system lacks validation to:
1. Prevent modification of metadata for tasks not in their expected state
2. Detect and prevent tasks from existing in multiple states simultaneously
3. Make the ID field truly immutable after creation

## Code Review Findings
After thorough examination of the codebase, I found **no code paths** in the normal hammer commands that would:
- Modify an existing task's ID after creation
- Incorrectly assign IDs during task creation or modification
- Cause the ID/branch mismatches observed

The ID is:
1. Set once during task creation (`tasks_ai/commands/create.py:68-89`)
2. Never modified in the modify command
3. Preserved during move operations (`tasks_ai/commands/move.py` and `tasks_ai/utils.py`)
4. Only readable, never written to, in all other commands

## Detection and Recovery Solution
I enhanced `tasks_ai/commands/list.py` to:
1. **Detect missing/corrupted IDs**: When `task.metadata.get("Id")` is missing or invalid
2. **Recover from directory name**: Extract numeric ID from directory format `{id}-{type}-{title}`
3. **Fix metadata automatically**: Write recovered ID back to meta.json
4. **Use reliable branch source**: Prefer `metadata.Br` when available, fallback to directory parsing
5. **Log recoveries**: Audit trail for when recoveries occur

## Prevention Recommendations
To prevent recurrence, consider implementing:

### 1. Id Immutability Validation
Add validation in modify/move operations to ensure ID never changes:
```python
# In modify.py and move.py, before writing task:
original_task = FM.load(original_path)
if original_task.metadata.get("Id") != task.metadata.get("Id"):
    cli.error("Task ID cannot be modified after creation")
```

### 2. State Consistency Checking
Add a validation that ensures a task ID exists in exactly one state:
```python
# In tasks doctor or validation command
def check_state_consistency(cli):
    id_locations = {}  # id -> list of (state, path)
    for state, folder in STATE_FOLDERS.items():
        fp = os.path.join(cli.tasks_path, folder)
        if not os.path.exists(fp):
            continue
        for item in os.listdir(fp):
            if item == ".gitkeep": 
                continue
            path = os.path.join(fp, item)
            task = FM.load(path)
            task_id = task.metadata.get("Id")
            if task_id:
                if task_id not in id_locations:
                    id_locations[task_id] = []
                id_locations[task_id].append((state, path))
    
    # Report IDs found in multiple locations
    inconsistencies = [id for id, locations in id_locations.items() if len(locations) > 1]
    if inconsistencies:
        cli.error(f"Task IDs found in multiple states: {inconsistencies}")
```

### 3. Metadata Validation
Add periodic validation that directory names match metadata:
```bash
# Could be added to 'hammer tasks doctor'
find .tasks -name "*-*-*" -type d | while read dir; do
  dirname=$(basename "$dir")
  id_from_dir=$(echo "$dirname" | cut -d'-' -f1)
  if [ -f "$dir/meta.json" ]; then
    id_from_meta=$(grep -o '"Id": [0-9]*' "$dir/meta.json" | cut -d' ' -f2)
    if [ "$id_from_dir" != "$id_from_meta" ] && [ "$id_from_meta" != "" ]; then
      echo "VALIDATION ERROR: dir=$dirname id_from_dir=$id_from_dir id_from_meta=$id_from_meta"
    fi
  fi
done
```

## Immediate Fix Applied
Modified `tasks_ai/commands/list.py` to automatically detect and recover from ID/branch mismatches by:
1. Recovering missing IDs from directory names when metadata is missing/corrupted
2. Using the trusted `metadata.Br` field for branch names when available
3. Falling back to directory parsing only when metadata is unavailable
4. Logging all recovery operations for audit and debugging

This fix ensures that `hammer tasks list` always displays correct information even when metadata corruption occurs, while providing visibility into when such recoveries are needed.

## Files Modified
1. `tasks_ai/commands/list.py` - Enhanced ID recovery and branch resolution logic

## Verification
After fix:
- All tasks display correct IDs matching their branch names
- No mismatches remain in `hammer tasks list` output
- Recovery operations are logged when metadata inconsistencies are detected