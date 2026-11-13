1. Add a reusable `.tasks/.gitignore` template constant with runtime-only ignore rules and the `!*.md` exemption.
2. Add a small init helper that creates the file and reconciles managed template entries while preserving unrelated entries.
3. Call the helper from production initialization.
4. Add and run focused regression tests for fresh initialization, repeated initialization, and Git tracking of Markdown files.