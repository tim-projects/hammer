---
Task: 232-task-restore-test-fixes
---

- Progress: Fixed test_init_already_initialized to expect failure on duplicate init. Added audit calls before --regression-check in test_regression_check_gate_blocks_staging, test_regression_workflow_cycle, test_delete_done_task_fails, test_branch_deletion_after_cleanup, and test_cleanup_merged_task. Fixed doctor test assertions to use bugs array instead of non-existent issues_found key. Updated UNFINISHED_CHECKBOXES hint and AGENTS.md to emphasize genuine criteria completion over cosmetic checkbox marking.
- Findings: ## Verified by code reading

**F1 — The test's config.yaml is destroyed by `init --force`.**
`setup_dev_config()` writes `config.yaml` into `dev_tasks_dir` BEFORE `run_dev(["init"], force=True)`. But `TasksCLI.init` does `shutil.rmtree(self.tasks_path)` (tasks_ai/cli.py:589) and the dev-mode clone path never re-creates `config.yaml` (cli.py:611-626). The stubbed `lint/test/type_check/format = /bin/true` is therefore wiped, so validation gates fall back to real tool detection.

**F2 — `init --dev` has no fallback; it hard-fails.**
cli.py:605-609 calls `self.error(...)` when the tasks-branch clone fails. Earlier session's "bare git init fallback" does not exist in the code.

**F3 — The id 311 proves the dev tasks store was not empty.**
`create` allocates ids via `_get_next_id()` -> `TaskCounterProtector.get_next_id()` (tasks_ai/counter.py:13-52), which falls back to `_recover_task_counter_from_tasks()`, a max-id directory scan (cli_engine.py:95-123). An empty store would yield id 1. Getting 311 means the store was a real clone of the tasks branch (max existing id 310). So `git clone --branch tasks` from the sandbox repo DID resolve.

**F4 — `TasksCLI._move_logic` swallows the return value.**
cli.py:1272-1276 calls `move_cmd.move_logic(...)` but has no `return`. Every internal caller that checks a result (delete.py:30, _auto_archive at cli.py:443, _reconcile_archive_all at cli.py:965, archive at cli.py:1000/1004) is silently receiving None.

**F5 — Enter hooks bypass `force=True`.**
move_logic passes `force=force` to `run_exit_hooks` (commands/move.py:133-135) but calls `run_enter_hooks` WITHOUT it (move.py:184-186). force=True paths (auto-archive, reconcile, delete, audit-failure rollback) therefore still execute BranchCheckHook, BranchExistsHook, CleanWorkspaceHook, ArchivedCommitHook, etc.

**F6 — move_logic's staged transition is fragile.**
move.py:164-212 copies the task to <tasks_path>/.ops/staging/<name>, runs enter hooks against the staged copy, then os.rename/merges into the target and rmtree's the original. The except Exception cleanup will NOT run if a hook terminates via SystemExit (which is what cli.error(...) does — cli.py:283-284 sys.exit(1)), leaking .ops/staging/<name> on every hook abort.

## Leading hypotheses for the task-vanishing bug (not yet proven)

**H1 — hook SystemExit during a forced/internal move** (F5 + F6): a hook calling cli.error aborts mid-move_logic, leaving state inconsistent and .ops/staging populated.

**H2 — .ops/staging name collision**: staged_task_path is keyed only on os.path.basename(filepath_str). Any basename reuse across concurrent test processes sharing one tasks dir would cross-contaminate.

**H3 — sandbox clone's branch topology**: because F3 shows real task data is present, the move chain operates against a full tasks-branch store, so every gate/hook is evaluated against hundreds of unrelated stale tasks. A single hook failure escalating to SystemExit mid-chain is far more likely in that environment than in an empty store.

- Mitigations: ## Recommended next steps (in priority order)

1. **Fix the test's config.yaml ordering bug (F1).** Move setup_dev_config(dev_tasks_dir) to AFTER run_dev(["init"], ...), or have it re-write the file post-init. This is a definite, proven test bug that causes spurious gate failures.

2. **Add per-step assertion helper in the integration test.** Every run_dev([...]) call should be checked: assert res.returncode == 0, f"{cmd} failed: {res.stdout}{res.stderr}". The current test ignores return codes for 11 consecutive commands, which is why the first real failure is invisible and surfaces only at the final step.

3. **Instrument the move chain with a find_task probe after each move.** Pinpoint the exact command at which the task disappears from the store. A simple os.listdir or run_dev(["list"]) after each transition would have answered this in one run.

4. **Inspect .ops/staging in a failing run.** If 311-task-integration-test-task is sitting in .ops/staging at failure time, H1 is confirmed and the fix belongs in move.py's exception handling (except BaseException / explicit SystemExit cleanup) plus honouring force in run_enter_hooks.

5. **Verify the sandbox clone's branch topology.** Because F3 proves real task data is present, confirm that git clone --single-branch --branch main still leaves origin/tasks accessible in the clone. Document the assumption.

6. **Fix _move_logic's missing return (F4).** Add the return in cli.py:1276. Low risk, restores correctness for four call sites.

7. **Clean up debug scaffolding before promotion.** tests/test_audit_verify_integration.py still contains the temporary os.walk dump and the LIST rc:/LIST stdout: prints added during debugging. Remove them and reconcile the task's pipeline state: 232 is recorded in backlog while its commits already reached TESTING.

