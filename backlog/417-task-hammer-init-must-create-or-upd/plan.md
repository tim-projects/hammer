1. 1. Add a reusable `.tasks/.gitignore` template constant with the Markdown rule and exceptions.
2. 2. Add a small init helper that creates the file and reconciles managed template entries while preserving unrelated entries.
3. 3. Call the helper from production initialization.
4. 4. Add and run focused regression tests for fresh and repeated initialization.