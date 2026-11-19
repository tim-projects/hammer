**Observed leftovers** (`ls -dt /tmp/hammer_tasks_*`): the dev stores AND, the expensive part,
a full git clone of the source repo per test at `<store>-repo` (contains AGENTS.md, README.md,
check.py, git history — ~300K and up each).

**Leak mechanics (verified in code + experiment):**
- `tests/hammer_test_base.py:52-53` — every test gets `tempfile.mkdtemp(prefix="hammer_tasks_")`
  as its dev store.
- `tasks_ai/context.py:88-91` (`dev_repo_path`) — the dev repo is `<store path>-repo`;
  `_ensure_dev_repo` (context.py:93+) clones the source repo into it on the CLI's first `--dev`
  invocation in that test. Path is keyed on the store, so a fresh mkdtemp per test can never
  reuse an existing clone.
- `tests/hammer_test_base.py:146-149` — `tearDown` does rmtree(test_root), rmtree(dev store),
  rmtree(dev repo, **ignore_errors=True**).
- Experiment (2026-11-09, main): `python3 -m pytest tests/test_init_backup.py -q` (2 passed)
  left +2 `/tmp/hammer_*` dirs. So a green, completed run still leaks: cleanup is not strict
  and/or is skipped on the path that test takes (ignore_errors masks failure; tearDown is not
  addCleanup, so setUp failures and killed runs also leak).
- Scale evidence: 1790 `/tmp/hammer_tasks_*-repo` dirs, `/tmp` 4.7G/4.7G tmpfs after roughly
  three full-suite runs plus in-repo work. A single clean suite run still leaves ~391M.
- Impact chain: ENOSPC → worktree adds, git writes and shutil fail → order-independent tests
  fail → suites cannot be trusted → CI signal destroyed.
