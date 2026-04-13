# Troubleshooting Guide

This guide covers common issues you may encounter when using Tasks AI and how to resolve them.

## Running Diagnostics

### Health Check

Run `tasks doctor` to diagnose task data integrity and git state:

```bash
tasks doctor
```

The doctor command checks:
- File structure (all 8 state folders exist)
- YAML metadata validity (Id, Ti, St, Cr fields)
- Markdown YAML frontmatter validation
- Orphan branch detection (branches without corresponding tasks)

## Common Issues

### Task Not Found

**Symptom**: `tasks: error: argument filename: invalid task ID: 'X'`

**Cause**: The task ID doesn't exist or you used the wrong ID.

**Solution**:
```bash
tasks list
# Use the numeric Id from the output (e.g., "17" not "17-task-...")
tasks show 17
```

### Cannot Move to PROGRESSING

**Symptom**: `Error: task requires story, tech, criteria, and plan`

**Cause**: Task doesn't have required fields populated.

**Solution**:
```bash
# Add required fields
tasks modify 17 --story "As a user..." --tech "Background..." --criteria "Criterion 1" --plan "Step 1"
```

### Cannot Move to TESTING

**Symptom**: `Error: must be on branch to move to TESTING`

**Cause**: You're not on the task's branch.

**Solution**:
```bash
# Switch to the task branch
git checkout 17-task-description

# Or use repo.py to handle branch switching
python repo.py promote 17
```

### Cannot Move to REVIEW

**Symptom**: `Error: tests must pass before moving to REVIEW`

**Cause**: Tests failed or haven't been run.

**Solution**:
```bash
# Run tests
tasks run test

# If tests pass, try moving again
tasks move 17 REVIEW
```

### Cannot Archive Task

**Symptom**: `Error: task must be merged to main before archiving`

**Cause**: Branch hasn't been merged to main.

**Solution**:
```bash
# Merge the branch using repo.py
python repo.py merge 17 to main

# Then archive
tasks move 17 ARCHIVED -y
```

### Branch Already Exists

**Symptom**: `error: pathspec 'branch-name' did not match any file(s)`

**Cause**: Branch was created but there's a path conflict, or branch exists on remote but not locally.

**Solution**:
```bash
# Check current branches
git branch -a

# If branch exists on remote, restore it
git checkout -b 17-task-description origin/17-task-description

# Or fetch and try again
git fetch origin
```

### Circular Dependency Detected

**Symptom**: `Error: circular dependency detected: X -> Y -> X`

**Cause**: Created a blocker relationship that forms a cycle.

**Solution**:
```bash
# Remove one of the blocker links
tasks unlink 17 18
```

### Merge Conflicts During Promotion

**Symptom**: Merge conflicts when using `python repo.py promote`

**Cause**: Branch has diverged from target branch.

**Solution**:
```bash
# Resolve conflicts manually
git checkout testing
git merge 17-task-description
# Fix conflicts, then commit

# Continue promotion
python repo.py promote 17
```

### Orphan Branches

**Symptom**: Doctor reports "orphan branch: branch-name"

**Cause**: Branch exists in git but no corresponding task file in task folders.

**Solution**:
```bash
# Option 1: Create missing task
tasks create "Task for branch-name" ...

# Option 2: Delete orphan branch
git branch -d branch-name
```

### Invalid YAML in Task File

**Symptom**: Doctor reports "invalid YAML" for a task

**Cause**: Task file has malformed YAML frontmatter.

**Solution**:
```bash
# Check the file
tasks show 17

# Fix the YAML manually - ensure proper format:
# ---
# Id: 17
# Ti: Title
# St: PROGRESSING
# ---
```

### Cannot Undo

**Symptom**: `Error: nothing to undo` or `Error: cannot undo past initial state`

**Cause**: No operation history or already at initial state.

**Solution**: Cannot undo further. Start fresh or manually edit task file.

### Cleanup Fails

**Symptom**: `Error: branch not pushed to remote`

**Cause**: Trying to delete a local branch that hasn't been pushed.

**Solution**:
```bash
# Push branch first
git push -u origin 17-task-description

# Then cleanup
tasks cleanup
```

### Branch Not Restored from Remote

**Symptom**: After moving archived task to PROGRESSING, branch doesn't exist locally

**Cause**: Branch may not have been pushed to remote previously.

**Solution**:
```bash
# Check if branch exists on remote
git fetch origin
git branch -r | grep 17-task

# If not on remote, you'll need to re-create the branch
git checkout -b 17-task-description
# Or the task may need to be recreated
```

### Configuration Issues

**Symptom**: `tasks run` fails with "command not found"

**Cause**: Configured tool not installed or not in PATH.

**Solution**:
```bash
# Check current config
tasks config list

# Update to installed tool
tasks config set repo.test pytest
tasks config set repo.lint ruff
tasks config set repo.type_check pyright
```

## Getting More Help

1. Run `tasks -h` for command help
2. Run `tasks <command> -h` for specific command help
3. Run `tasks doctor` for data integrity checks
4. Check git status: `python repo.py status`
5. List all branches: `python repo.py branch list`