
- Progress:
  - Root cause: two independent check entry paths, both resolve config from the
    *invocation* root. A task worktree has no .tasks (the store lives only in the
    main repo), so Validator/check.py find no repo.lint/test/... config and abort
    with "Tool 'lint' (None) not configured or not supported".
  - Fixed in both paths:
    * check.py find_project_root: a worktree's .git FILE now counts as a project
      root (was isdir), so a worktree resolves to itself, not the main repo.
    * check.py get_main_repo_root() (git rev-parse --git-common-dir, cwd-aware
      for relative paths) + load_config falls back to the main repo's store
      config when the local .tasks is absent.
    * tasks_ai/validator.py _store_config_path(): same fallback for the
      hammer check wrapper path; tool resolution now maps any configured
      command PATH to a known tool by basename (was: /bin/ prefix only).
    * tasks_ai/check_wrapper.py resolves the project root via
      git rev-parse --show-toplevel instead of "." so subdirectory invocations
      validate the whole tree.
    * Removed the .last_validation_hash short-circuit from check.py run_all and
      validator.run_all (plus the dead hash readers/writers). It silently
      skipped all validation on main whenever HEAD matched, hiding breakage.
  - gate (tasks move) unaffected: it runs check.py with
    HAMMER_DEV_TASKS_DIR already pointing at the store.
  - Tests: tests/test_check_worktree.py (6) - fixture is a real main repo +
    git worktree + store config with path-valued tools; runs check.py all and
    ./hammer check all from the worktree and a subdir, asserts real tool
    results, path-valued tool execution, and no silent skip.
  - Verified: ruff clean on changed files; tests/test_check_worktree.py,
    tests/test_store_writes.py, tests/test_guard.py, tests/test_cli_endpoints.py
    pass (38 + 11).