1. Add Rc metadata field tracking in constants.py
2. Create _generate_review_diff method in cli.py
3. Hook diff generation into REVIEW state transition
4. Implement REVIEW->STAGING gate checking Rc field
5. Add --regression-check flag to modify command
6. Update help_text.py with regression check info
7. Update AGENTS.md with verification instructions
8. Update README.md with usage examples
9. Update repo.py help text if needed
10. Write test_tasks.py tests for diff generation and Rc gate
11. Write test_robustness.py tests for edge cases
12. Write test_dev_mode.py tests for dev mode
13. Test diff file location and content
14. Test agent instruction output on REVIEW move
15. Verify all existing tests still pass
16. Run lint, typecheck, and full test suite
