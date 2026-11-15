1. 1. Add focused tests that create a task branch with recorded commits, contain it in the main branch, remove local staging, and assert the exact approved output plus absence of misleading merge messages
2. 2. Add negative tests for a real merge, an empty branch, and a resolved source with additional commits
3. 3. Refactor merge execution to report whether it created a merge commit or found the target already up to date
4. 4. Connect the no-op result to the fast-track DONE promotion and emit the exact approved one-line message while suppressing misleading intermediate lines
5. 5. Verify text and JSON output, then run the focused and existing promotion test suites
6. 6. Promote through the standard pipeline to DONE