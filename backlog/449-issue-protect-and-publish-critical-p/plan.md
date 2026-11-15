1. 1. Research the installed hook lifecycle and Git's supported local branch-deletion hook mechanism, including common hooks path behavior for linked worktrees.
2. 2. Add a critical-branch deletion guard for local Git operations and an explicit guard in hammer repo branch delete.
3. 3. Make pipeline promotion ensure local testing and staging exist, merge every task through both intermediate branches, and push each branch after its gate.
4. 4. Add user-level regressions for deletion protection and TESTING/STAGING/DONE remote publication.
5. 5. Run focused hook, repo, and pipeline tests, then the full validation suite.
6. 6. Review the diff, run the regression check, and promote the task through the pipeline.