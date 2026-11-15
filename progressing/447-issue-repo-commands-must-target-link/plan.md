1. 1. Add a regression test that runs repo commands from a linked worktree and proves they resolve the worktree root and branch.
2. 2. Change repo root resolution to use git rev-parse --show-toplevel before the non-Git fallback.
3. 3. Add .tasks-repo to ignore rules and verify neither repo commit nor transition auto-commit stages it.
4. 4. Run focused repo and pipeline tests, then the full validation suite.
5. 5. Review the diff, run the regression check, and promote the task through the pipeline.