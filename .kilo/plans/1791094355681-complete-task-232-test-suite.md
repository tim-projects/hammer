# Plan: Complete task 232 — branch prep, PROGRESSING, debug, pass

## Current state

- HEAD is `main` at `95e6f03`, 7 commits ahead of `origin/main`.
- Branch `232-task-restore-test-fixes` exists at `888721a` — **behind** main and **missing** the current test fixes.
- Working tree on `main` has uncommitted fixes:
  - `tests/hammer_test_base.py` — staged (detach/fetch/branch-setup logic, `.ops` cleanup)
  - `tests/test_audit_verify_integration.py` — unstaged (hermetic rewrite with debug scaffolding still inside)
- The fixes need to be on `232-task-restore-test-fixes` before the task can progress through the pipeline.

## Verified findings (unchanged from prior session)

**F1** — `setup_dev_config(dev_tasks_dir)` writes `config.yaml` before `init --force`, but `TasksCLI.init` does `shutil.rmtree(self.tasks_path)` at `tasks_ai/cli.py:589` and never recreates `config.yaml` (`cli.py:611-626`). Validation stubs are wiped.

**F2** — `init --dev` has no bare-init fallback; `cli.py:605-609` hard-errors on clone failure.

**F3** — Allocated id 311 proves the dev tasks store was a real clone of the `tasks` branch (max id 310). `git clone --branch tasks` from the sandbox repo resolved.

**F4** — `TasksCLI._move_logic` at `cli.py:1272-1276` calls `move_cmd.move_logic(...)` but has no `return`. Four internal callers silently receive `None`.

**F5** — `run_enter_hooks` in `tasks_ai/hooks.py:22-25` takes no `force` parameter, so `force=True` paths still execute enter hooks (`BranchCheckHook`, `BranchExistsHook`, `CleanWorkspaceHook`, `ArchivedCommitHook`).

**F6** — `move_logic` staged-transition cleanup in `tasks_ai/commands/move.py:208-212` uses `except Exception`, which does **not** catch `SystemExit`. Hooks calling `cli.error(...)` → `sys.exit(1)` leak `.ops/staging/<name>`.

## Hypothesis for task-vanishing

**H1** — hook `SystemExit` during a forced/internal move (F5 + F6): a hook aborts mid-`move_logic`, leaving `.ops/staging` populated and the original task in an indeterminate state.

**H2** — `.ops/staging` name collision: `staged_task_path = tasks_path/.ops/staging/<basename>`; concurrent processes sharing a tasks dir could cross-contaminate.

**H3** — sandbox clone has full `tasks`-branch data, so hooks evaluate against hundreds of stale tasks; a single `SystemExit` is more likely there than in an empty store.

## Ordered execution steps

### Step 1 — Put all current fixes onto the task branch

On `main`, the fixes are split: `tests/hammer_test_base.py` is staged, `tests/test_audit_verify_integration.py` is unstaged.

```
git checkout 232-task-restore-test-fixes
git merge main --no-edit
```

This merges main's 7 auto-commits plus the working-tree fixes onto the task branch in one shot. Resolve any conflicts if they arise (unlikely since the branch is a strict ancestor of main).

After the merge:
- `232-task-restore-test-fixes` contains all current code and fixes.
- The task branch is no longer behind main.

### Step 2 — Move task 232 to PROGRESSING via the pipeline

```bash
./hammer tasks move 232 PROGRESSING
```

This triggers the pipeline hooks (`TaskRepairHook`, `ContentSufficiencyHook`, `BlockerCheckHook`, `BranchCheckHook`, `BranchSyncHook`) and commits the state transition. If it fails, the hook output will tell us exactly why.

### Step 3 — Remove debug scaffolding from the integration test

In `tests/test_audit_verify_integration.py`:
- Delete lines 70-79 (`os.walk(dev_tasks_dir)` dump).
- Delete lines 100-102 (`LIST rc` / `LIST stdout` prints).
- Leave the hermetic structure (temp dirs, `cwd=`, `check=True`) intact.

### Step 4 — Fix the `config.yaml` ordering bug (F1)

Move `setup_dev_config(dev_tasks_dir)` to **after** `run_dev(["init"], force=True, cwd=repo_dir)` in the integration test. This is the simplest, lowest-risk fix.

Alternatively (preferred long-term): have `TasksCLI.init` write a default `config.yaml` in dev mode after `cli.py:623`, so callers don't need to manage it. Do the test-side fix first; the init-side fix can be a separate follow-up if desired.

### Step 5 — Add per-step assertions

Add a small helper in the integration test:
```python
def check(label, result):
    assert result.returncode == 0, (
        f"{label} failed (rc={result.returncode}): "
        f"{result.stdout[:500]} {result.stderr[:500]}"
    )
```

Replace every bare `run_dev([...])` with `check("...", run_dev([...], cwd=repo_dir))`. Add `check=True` to every `subprocess.run` that is missing it. This makes the first failing step visible instead of surfacing only at the final assertion.

### Step 6 — Run the integration test and capture the new failure point

```bash
pytest tests/test_audit_verify_integration.py -x --tb=short -s 2>&1 | tee /tmp/232_test_run.txt
```

Do **not** grep-filter the output. Read the full file. The new per-step assertions will pinpoint exactly which transition fails.

### Step 7 — Debug based on the failure point

**If the task disappears mid-chain (H1 suspected):**
- Add a probe before the `finally` block:
  ```python
  ops_staging = os.path.join(dev_tasks_dir, ".ops", "staging")
  if os.path.exists(ops_staging):
      print("STAGING LEAK:", os.listdir(ops_staging))
  ```
- Also add `run_dev(["list"], cwd=repo_dir)` after each transition to see whether `data: {}` appears.
- If `.ops/staging` contains the task dir, H1 is confirmed.

**If `_auto_archive` fires on a non-DONE task (sanity check):**
- Confirm `_auto_archive` only iterates `STATE_FOLDERS["DONE"]` (`cli.py:415`). If a task in `progressing`/`review` is being moved, the cause is elsewhere.

**If validation gates fail due to missing `config.yaml`:**
- Step 4's fix should have resolved this. If not, fall back to the init-side `config.yaml` write.

### Step 8 — Apply the targeted code fix

Based on Step 7's diagnosis, apply **one** of:

- **H1 confirmed**: Fix `move.py:208-212` — change `except Exception` to `except BaseException` so staging cleanup runs on `SystemExit` too. Also fix `hooks.py:22-25` — add `force=False` to `run_enter_hooks` and have `move.py:184-186` pass it. This is a two-line change in each file.
- **H2 confirmed**: Make `staged_task_path` unique per invocation (e.g., include PID or a UUID in the staging dir name).
- **H3 confirmed**: The integration test's temp tasks dir is already hermetic; if the problem is stale task data from a full clone, ensure `init --force` always wipes and re-clones cleanly (verify `shutil.rmtree` + clone sequence in `cli.py:583-609`).

### Step 9 — Fix `_move_logic` missing return (F4)

In `tasks_ai/cli.py:1276`:
```python
return move_logic(self, filename, new_status, force=force, yes=yes, sync=sync)
```

This is a one-line, low-risk fix that restores correctness for `delete.py:30`, `_auto_archive`, `_reconcile_archive_all`, and `archive`.

### Step 10 — Re-run and iterate

```bash
pytest tests/test_audit_verify_integration.py -x --tb=short
pytest tests/ -x --tb=short
./hammer check all
```

Iterate until the full suite passes. Each iteration should change the failure mode or produce a green run.

### Step 11 — Clean up the task record

Once green:
1. Commit the cleaned test files on `232-task-restore-test-fixes`.
2. Run `./hammer tasks modify 232 --tests-passed --reviewed --regression-check`.
3. Move through the pipeline:
   ```bash
   ./hammer tasks move 232 TESTING
   ./hammer tasks move 232 REVIEW
   ./hammer tasks modify 232 --regression-check
   ./hammer tasks move 232 STAGING
   ./hammer tasks move 232 DONE
   ```
4. Only after `./hammer check all` is green, archive.

## Validation criteria (all must be true before STAGING)

1. `pytest tests/test_audit_verify_integration.py` passes.
2. `pytest tests/` full suite passes.
3. `./hammer check all` passes (lint, typecheck, format, test).
4. `tests/test_audit_verify_integration.py` and `tests/hammer_test_base.py` contain no debug scaffolding.
5. `git diff --stat` on the task branch shows only the intended clean set of changes.
6. Task 232's `.tasks/` metadata state matches its actual pipeline position.

## Key risk

The `232-task-restore-test-fixes` branch is an ancestor of `main` by many commits. Merging `main` into it (Step 1) will bring in all the auto-commits and the uncommitted fixes at once. If the merge produces conflicts in `tasks_ai/` source files, resolve them in favor of `main`'s versions (those are the tested ones). The test files should merge cleanly since the branch is strictly behind.
