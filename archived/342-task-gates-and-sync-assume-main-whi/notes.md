
- Progress: gate/sync/merge/archive paths now resolve the real default branch.
- Root cause: get_default_branch probed main/master but every caller
  hardcoded 'main' (or relied on its old unconditional fallback), so a
  master-named repo compared against a branch git does not have.
- Changes:
  - git_service.get_default_branch -> str | None (origin/HEAD, then first
    existing of main/master; None when neither exists).
  - is_merged target defaults to the derived default branch.
  - check_main_divergence, sync_pipeline, promote_task (pipeline_map),
    demote_task use the derived branch.
  - pipeline.validate_gate: fast-track + integration target derived; new
    NO_DEFAULT_BRANCH gate for DONE/ARCHIVED (errors.json/hints.json).
  - cli.py archive scans, commands/move.py ARCHIVED check,
    worktree_manager branch cleanup, cleanup, utils/cli sync_task_content,
    pipeline_hooks sync hooks all resolve the default branch (None-safe).
- Tests: tests/test_default_branch.py - master-named repo promotes end to
  end (create->READY->PROGRESSING->checkpoint->TESTING->REVIEW->STAGING->
  DONE->ARCHIVED); trunk repo (no main/master) fails with an actionable
  error; unit checks for get_default_branch/is_merged; grep guard that no
  gate-path file still hardcodes main.
- Skipped: the four bash hook strings in cli.install_hooks still name
  'main' (install-time static text, not a gate path; existing installs are
  unaffected). Master repos would not be protected by the pre-commit
  branch-name / pre-merge guards until those strings are made dynamic.
- Verified: ./hammer check all passes (lint/test/typecheck/format);
  pre-existing failure test_repo.py::test_repo_save_with_mock_remote
  reproduced on pristine main.