## Implementation in repo.py

### 1. Enhance resolve_branch()
Currently `resolve_branch()` in repo.py line ~167 already has some task ID handling but it only works when the input is purely numeric. We need to enhance it to:
- Check if input contains a numeric ID (e.g., "89-task-fix-something" contains "89")
- Use TasksCLI to look up the task and get its branch
- Return the full branch name

```python
def resolve_branch(name):
    if name == "current":
        return get_current_branch()
    
    # Extract numeric ID if present (e.g., "89-task-xxx" -> "89")
    numeric_id = name.split("-")[0] if name else None
    if numeric_id and numeric_id.isdigit() and TasksCLI:
        cli = TasksCLI(quiet=True, dev=FLAGS["dev"], yes=FLAGS["yes"])
        path, _ = cli.find_task(numeric_id)
        if path:
            branch_name = os.path.basename(path)
            return branch_name
    
    if branch_exists(name):
        return name
    error(f"Could not resolve branch: {name}")
```

### 2. Update cmd_merge error handling
When `ensure_pipeline_branch()` fails because the target is not in PIPELINE, we should:
- Catch the error gracefully
- Instead of failing, proceed with the merge
- Provide informative logging about what's happening

### 3. Add confirmation prompt (optional, for non -y mode)
When merging between task branches (outside pipeline), prompt:
```
Merging between task branches (outside pipeline).
This will merge SOURCE_BRANCH into TARGET_BRANCH. Continue? [y/n]
```

### 4. Key functions to modify
- `resolve_branch()` - enhance to extract and resolve numeric IDs
- `cmd_merge()` - update error handling for non-pipeline targets
- `ensure_pipeline_branch()` - gracefully handle non-pipeline cases