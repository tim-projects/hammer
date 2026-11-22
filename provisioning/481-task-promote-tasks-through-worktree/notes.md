
- Progress:
  - Reworked TESTING, STAGING, and PR promotions to merge task-local `<id>-<STAGE>` refs in the task worktree.
  - Missing stage refs are created at the previous stage tip before the merge; non-dev promotions publish the stage ref.
  - Shared terminal promotion behavior is unchanged.
  - Added isolation, missing-tip, worktree-list, and concurrent-promotion regression coverage.
  - Updated affected pipeline tests that previously asserted shared `testing`/`staging` refs.
  - Validation: `./hammer check all` passes lint, tests, typecheck, and format.