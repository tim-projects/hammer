---
Task: 85-task-automated-pr-review-workflow
---


- Progress: COMPLETE - Automated PR review workflow implemented and tested.
- Changes Made:
    1. Added `Rv` (ReviewedFiles) to constants.py KEY_MAP
    2. Updated help_text.py with new review workflow instructions
    3. Added `_parse_diff_summary()` method in cli.py to parse diff files
    4. Modified `_generate_review_diff()` to create .summary file
    5. Added `review()` method in cli.py with --list, --show, and file confirmation
    6. Added review subcommand in tasks.py
    7. Updated regression check gate to require both Rc AND Rv
    8. Rc reset now also clears Rv; REVIEW entry resets both
- Test Results:
    - test_review_workflow.py passes fully
    - New workflow: create -> TESTING -> REVIEW -> review --list -> review <file> -> --regression-check -> STAGING
    - Pre-existing test_robustness.py failure (unrelated)