RESEARCH (479 - <id>-<STAGE> branch naming):
- Verified: guard_engine.py:45 BRANCH_CONVENTION_RE = ^(\d+)-(task|issue|docs)-[a-zA-Z0-9-]+$ ; utils.py:57 derive_task_id builds <id>-<type>-<slug>; the pre-commit hook template that installs the same regex is written in cli.py:631 (install_hooks).
- Task FOLDER names stay <id>-<type>-<slug> (task records, audit siblings, review paths depend on them) - only the branch naming changes, and only for tasks created after this change.
- Rationale: git refs are repo-wide; a branch cannot be checked out in two worktrees. Stage refs must be unique per worktree: <id>-PROGRESSING/-TESTING/-STAGING/-PR.
- Hook reinstall needed once after the template change (fresh repos are fine).
- Check-merged/repo merge commands resolve names via resolve_branch (repo.py:411-423) - stage names must not collide with that resolution.
