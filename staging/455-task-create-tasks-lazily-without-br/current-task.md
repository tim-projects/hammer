---
Task: 455-task-create-tasks-lazily-without-br
---

- Implemented lazy task creation: primary and paired tasks persist metadata without creating local branches, worktrees, or manifest entries.
- Changed create output to report a planned branch and return `worktree: null`.
- Allowed BACKLOG/READY tasks to pass guard checks without local Git state while retaining duplicate-ID detection against planned task branches.
- Prevented transitions without a worktree from auto-committing the main checkout (which could capture `.tasks` into the task branch).
- Added `tests/test_lazy_task_creation.py` covering primary/pair laziness, output, metadata/counter/priority/parent preservation, and BACKLOG/READY lifecycle.
- Updated existing suites that intentionally exercised worktree behavior to mount explicitly.
- Verification: 115 affected tests passed; ruff check and ruff format check passed.
