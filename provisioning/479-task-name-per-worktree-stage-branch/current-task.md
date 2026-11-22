---
Task: 479-task-name-per-worktree-stage-branch
---

Implemented per-task stage branch naming and separated task folders from git branches. Guard/hook accept PROGRESSING, TESTING, STAGING, PR; branch consumers now use metadata.Br. Ruff passes; affected suites pass. Full suite has two main-branch failures tracked by task 505.