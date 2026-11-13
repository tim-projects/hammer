
- Progress: 

Landing notes:
1. Fixture model discovered: HammerTestBase clones os.getcwd() and then
   forces 'main' to origin/main, so harness tests run MAIN's code; branch code
   only reaches them through per-test copy lists (pattern from test_unlink).
   test_repo now copies the branch's hammer/tasks.py/cli.py/git_service.py/
   utils.py/data files and commits them in the fixture.
2. The in-suite cascade was env/cwd leakage: restores are now registered in
   setUp via addCleanup BEFORE any mutation, so a mid-test failure cannot leak
   HAMMER_DEV_TASKS_DIR or a deleted cwd into later files.
3. Dev push policy is one helper (GitService.dev_push_allowed): a dev push is
   allowed only to a remote the store was deliberately given (mock remotes);
   the parent repo's remote, no remote, and the throwaway dev repo itself are
   all refused. TasksCLI.save errors with DEV_COMMAND_REFUSED from the same
   policy; push_tasks_branch keeps its own guard for the hook path. The
   parent-remote fallback that wired dev stores to the real repo is
   unreachable in dev.
4. tasks upgrade is refused in dev (DEV_WRITE_BLOCKED): install.sh writes the
   live installation. Code registered in data/errors.json + data/hints.json.
5. tests/test_dev_write_audit.py pins the invariant (5 tests): full dev
   workflow leaves the invoked repo byte-identical; the store is never wired to
   the production remote; upgrade refused; worktrees under the dev repo; a
   mock-remote save is not refused by dev.
6. All six previously-failing families (store_writes, worktree_system,
   require_task_id, store_concurrency, worktree_ownership_user,
   task_naming_user) pass standalone on the branch after the fixture fix.