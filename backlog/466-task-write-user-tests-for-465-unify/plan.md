1. 1. Define the JSON and terminal contracts for genuine errors and next-step stalls in `tasks_ai/cli_io.py` and `tasks_ai/messages.py`.
2. 2. Convert parser-generated usage stalls to `NEXT STEP:` / `status: next_step` and update parser consumers.
3. 3. Convert validation/check result statuses and wording from blocker to next-step, preserving tool diagnostic codes.
4. 4. Classify and convert pipeline/command prerequisite gates from error to next-step; retain genuine failure codes.
5. 5. Expose stable error codes for genuine JSON errors and remove error-code semantics from next-step responses.
6. 6. Update `AGENTS.md`, help text, documentation, fixtures, and tests for the single convention.
7. 7. Run focused tests, full suite, lint, and type checks; verify temporary-directory cleanup remains bounded.