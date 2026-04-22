## Acceptance Criteria

### Must Have
- [ ] `python repo.py merge 89 to 88 -y` works without error
- [ ] `python repo.py merge 89-task-xxx to 88-task-yyy -y` works
- [ ] `python repo.py merge testing to staging -y` still works (pipeline merges)
- [ ] Clear log output showing what is being merged

### Should Have
- [ ] Without `-y`, prompts for confirmation before cross-branch merge
- [ ] Error message is helpful, explains what went wrong if ID not found

### Tests
- [ ] Add test case for merging between task branches using numeric IDs
- [ ] All existing tests still pass