
- Progress: hooks and repo wrapper now resolve the actual default branch.
- Root cause: install_hooks wrote static bash naming 'main', and repo.py
  hardcoded the pipeline top. On a master-named repo the pre-commit hook
  rejected every commit on the default branch (branch-name regex gate).
- Changes:
  - tasks_ai/cli.py install_hooks: one default_branch_snippet (origin/HEAD,
    then first existing of main/master, final fallback main) interpolated into
    all four hooks; pre-merge renamed to pre-merge-commit (the real git hook
    name - 'pre-merge' never fires) and now exempts HAMMER_INTERNAL_CALL=1 so
    hammer's own merges still work; post-merge/pre-receive use the resolved
    branch.
  - repo.py (the script 'hammer repo' runs): get_default_branch()/pipeline()
    helpers replace PIPELINE; check_merged_to_main, ensure_pipeline_branch,
    cmd_merge target guard, cmd_sync and the pipeline_to_status map resolve
    the default branch; run() sets HAMMER_INTERNAL_CALL=1 so 'repo merge'/
    'repo sync' are not blocked by the new pre-merge-commit hook.
  - Note: tests/repo.py is a stale unused copy (hammer dispatches to the root
  repo.py); left untouched deliberately.
  - guards: guard.py has its own separate PRE_COMMIT/PRE_PUSH hook bodies
  (guard scanning, unrelated to the main hardcode) - untouched.
- Tests: tests/test_hooks_default_branch.py - 15 tests. Generated hooks contain
  the resolution; pre-commit allows commits on master and still blocks
  nonconformant branches; pre-merge-commit blocks a direct merge into master
  and into main (regression) but not hammer's own merges; post-merge reports
  in-sync against master; pre-receive blocks deleting master on a bare remote
  while allowing feature branch deletes; repo.py pipeline() resolves master
  and main.
- Verified: ./hammer check all passes (lint/test/typecheck/format).