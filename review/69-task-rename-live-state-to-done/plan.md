1. Investigate all LIVE references using grep
2. Create branch 69-task-rename-live-state-to-done
3. Update constants.py: STATE_FOLDERS, ALLOWED_TRANSITIONS
4. Update cli.py: all LIVE references
5. Update help_text.py: state machine
6. Update AGENTS.md: promotion workflow
7. Update README.md: state machine and commands
8. Update repo.py: help text
9. Update test_tasks.py: all LIVE references
10. Update test_robustness.py: all LIVE references
11. Rename .tasks/live to .tasks/done in local worktree
12. Implement auto-migration in TasksCLI.__init__ or find_project_root
13. Add tasks doctor --migrate-live command
14. Verify backward compatibility
15. Run all validation (lint, typecheck, tests)