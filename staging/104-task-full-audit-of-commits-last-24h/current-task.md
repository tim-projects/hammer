---
---


# Audit Findings
- Found "hammer tasks-ai" branding artifacts in `install.sh`, `hammer tasks_ai/cli.py`, `bug-report.md`, and `tests/hammer tasks_ai/cli.py`.
- Found inconsistent "HAMMER" voice usage in CLI output vs. documentation.
- Git merge conflicts caused loss of branding changes in `README.md` and related files.

# Plan
1. Systematically rename `hammer tasks-ai` to `hammer` in paths, file naming, and docs.
2. Harmonize all CLI output to strictly follow HAMMER VOICE rules.
3. Update failing test expectations to reflect branding changes.
4. Perform final verification using `check.py all`.