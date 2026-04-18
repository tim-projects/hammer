- Progress: Implemented automated PR review workflow in cli.py and tasks.py.
- Changes Made:
    1. Added `Rv` (ReviewedFiles) to constants.py KEY_MAP
    2. Updated help_text.py with new review workflow instructions
    3. Added `_parse_diff_summary()` method in cli.py to parse diff files
    4. Modified `_generate_review_diff()` to create .diff.summary file
    5. Added `review()` method in cli.py with --list, --show, and file confirmation
    6. Added review subcommand in tasks.py
    7. Updated regression check gate to require both Rc AND Rv
    8. Rc reset now also clears Rv; REVIEW entry resets both
- Next Steps:
    1. Run tests in --dev environment to verify workflow
    2. Move to TESTING and promote