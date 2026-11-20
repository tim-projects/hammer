---
Task: 475-task-configure-unref-checks-for-thi
---

- Progress: Installed unref 0.3.2 in project venv and as a user-level uv tool for worktrees. Enabled repo.lint_secondary=unref in shared Hammer config. Added path-scoped baseline for 45 existing findings in pyproject.toml. Direct unref exits 0; hammer check lint passes; temporary newly_unreferenced_probe was detected and blocked with exit code 1.
- Findings: Existing baseline uses path-scoped overrides so new unused symbols in active files remain detectable.
- Mitigations: No active source tree is excluded and no used-name is globally whitelisted.
