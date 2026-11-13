1. Add a focused integration test for fresh task-store initialization and its generated `.tasks/.gitignore`.
2. Add assertions that all Markdown files are exempt from ignore processing and tracked by Git.
3. Add assertions for runtime-only, cache, and scratch exclusions without excluding persistent task data.
4. Add an idempotency assertion for repeated initialization.
5. Run the focused test suite and the project validation checks.