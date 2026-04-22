As a developer using the tasks CLI, I want to merge between task branches using their numeric IDs so I don't have to remember full branch names.

Currently when I run `python repo.py merge 89 to 88 -y`, it fails with "Branch 89 not in pipeline" because:
- The command only accepts pipeline branch names (testing, staging, main)
- It doesn't recognize numeric task IDs as valid inputs
- Task branches are outside the pipeline

**Desired behavior:**
- Accept numeric task IDs as source/target in merge command
- Automatically resolve ID to corresponding branch name
- On pipeline error, catch it and provide a helpful prompt explaining the merge will happen outside the pipeline
- With `-y` flag, auto-confirm without prompting

**Examples:**
```
# Should work: merge task 89's branch into task 88's branch
python repo.py merge 89 to 88 -y

# Should also work with branch names
python repo.py merge testing to staging -y
```