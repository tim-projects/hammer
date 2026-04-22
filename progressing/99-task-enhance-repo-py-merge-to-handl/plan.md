1. **Read and understand current code**
   - Review `resolve_branch()` function in repo.py
   - Review `cmd_merge()` function in repo.py  
   - Review `ensure_pipeline_branch()` function in repo.py
   - Understand how task ID resolution currently works

2. **Enhance resolve_branch()**
   - Extract numeric ID from inputs like "89-task-xxx"
   - Use TasksCLI.find_task() to look up task and get branch
   - Return full branch name

3. **Update error handling in cmd_merge()**
   - Modify `ensure_pipeline_branch()` to not error on non-pipeline targets
   - Instead, just check if branch exists and proceed
   - Log informative message about cross-branch merge

4. **Test the changes**
   - Test: `python repo.py merge 89 to 88 -y` (should work)
   - Test: `python repo.py merge testing to staging -y` (should still work)
   - Test: `python repo.py merge 89 to 88` (should prompt without -y)
   - Verify all existing tests pass

5. **Run validation**
   - `python check.py all`
   - Ensure lint, typecheck, tests all pass