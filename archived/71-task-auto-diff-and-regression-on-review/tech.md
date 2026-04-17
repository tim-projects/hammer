Auto-generate diff file on REVIEW transition, add regression check gate (Rc checkbox) before STAGING.

## Files to Update

### Core Python Files
1. **tasks_ai/constants.py**:
   - Add `"Rc": "RegressionCheck"` to KEY_MAP for display
   - Update AGENT_GUIDANCE to mention regression check gate (line 56+)

2. **tasks_ai/cli.py**:
   - Add `_generate_review_diff(self, task_path, branch)` method:
     - Get diff against main: `git diff main...HEAD` (includes unstaged)
     - Also capture any unstaged changes: `git diff` (working tree)
     - Combine and save to `.tasks/review/<task_id>/diff.patch`
     - Return path to diff file
    - In `_move_logic`, when `new_status == "REVIEW"`:
      - Call `_generate_review_diff` after task move
      - Set `task.metadata["Rc"] = ""` (unset)
      - Log message: "Regression diff generated at .tasks/review/<task_id>/diff.patch. Review diff for regressions. If regressions found, move task back to PROGRESSING/TESTING to fix before proceeding. Once clean, run 'tasks modify <id> --regression-check' to confirm and allow promotion to STAGING."
   - Add gate before allowing `new_status == "STAGING"` from REVIEW:
     ```python
     if current_state == "REVIEW" and new_status == "STAGING":
         task = FM.load(filepath_str)
         if not task.metadata.get("Rc", False):
             self.error(
                 "Cannot move to STAGING: regression check not passed.",
                 hint="Review the diff at .tasks/review/<task_id>/diff.patch, then run 'tasks modify <id> --regression-check' to confirm no regressions."
             )
     ```
   - Add `--regression-check` flag to `modify` command:
     - Sets `task.metadata["Rc"] = True`
     - Saves task file
     - Log confirmation

3. **tasks_ai/help_text.py**:
   - Update STATE MACHINE diagram/notes to include regression check gate
   - Add example: `tasks modify <id> --regression-check`

### Documentation
4. **AGENTS.md** (lines 41-54): Add step: "Before moving REVIEW→STAGING, verify regression diff at .tasks/review/<id>/diff.patch"
5. **README.md**:
   - Document new `--regression-check` modify flag
   - Update state machine diagram to show Rc gate
   - Add usage example for regression check
   - Document regression workflow: if regressions found, move back to PROGRESSING/TESTING

### Tests
6. **test_tasks.py**:
   - Test: moving to REVIEW creates diff.patch
   - Test: moving REVIEW→STAGING without Rc fails
   - Test: `modify --regression-check` sets Rc and allows STAGING
7. **test_robustness.py**:
   - Similar tests for regression check gate
8. **test_dev_mode.py** (if relevant): Test diff generation in dev mode

### Tools
9. **repo.py**: Update any help text mentioning review workflow

## Implementation Notes

### Diff Generation
- Use `git diff main...HEAD --patch` to get branch commits vs main
- Combine with `git diff` (unstaged working tree changes)
- Save as unified diff patch in `.tasks/review/<task_id>/diff.patch`
- Create review folder if not exists: `os.makedirs(review_dir, exist_ok=True)`

### Regression Found Workflow
- Agent reviews diff at `.tasks/review/<task_id>/diff.patch`
- If regressions detected: agent should run `tasks move <id> PROGRESSING` (or TESTING) to send task back for fixes
- Developer fixes code, then re-moves through TESTING → REVIEW (new diff auto-generated)
- Once diff is clean, agent runs `tasks modify <id> --regression-check`
- Then `tasks move <id> STAGING` is allowed

### Metadata Field
- `Rc` = Regression check passed (boolean, stored as string "True"/empty)
- Display in task metadata similar to `Tp` (Tests passed)
- Default: unset (False) when entering REVIEW

### Backwards Compatibility
- Existing tasks: when first moved to REVIEW, diff generated automatically; Rc defaults to unset
- No breaking changes to existing workflow

### Branch Naming
Branch: `71-task-auto-diff-and-regression-on-review`
