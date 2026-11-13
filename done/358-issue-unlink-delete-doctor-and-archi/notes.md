
- Progress: 

## Change

Six store-mutating sites used a store-wide `git add --all` in the shared
`.tasks` repo. Four are per-task and now route through `commit_task_paths`
(scoped pathspec, STORE_WRITE_FAIL on failure, already store-locked):

- `tasks_ai/commands/unlink.py` - commits the unlinked task's record only
- `tasks_ai/commands/delete.py` - records the permanent delete of that task's
  paths only (`_stageable` already resolves the now-deleted paths)
- `tasks_ai/commands/doctor.py` - the `--fix` repair commits the task's new and
  old paths; the old try/except "Warning: Could not commit fixes" was dropped
  because `commit_task_paths` fails loudly (cli.error exits, so the old
  except-Exception never caught it anyway)
- `tasks_ai/pipeline_hooks.py` `ArchivedCommitHook` - scoped to the task's
  staged copy (`.ops/staging/<name>`) plus the old state folder, BEFORE the
  push, so only the archived task's own state reaches origin. The hook runs as
  an enter hook, so the physical `archived/` path lands in the move's own
  commit (`commands/move.py`), unchanged.

Two sites legitimately touch the whole store and now hold the store lock with
a comment saying why they cannot be scoped:

- `tasks_ai/cli.py` `_migrate_live_to_done` (every LIVE record moves)
- `tasks_ai/cli.py` `_clear_delete_marks` (a mark can sit in any state folder)

## Tests (`tests/test_store_writes.py`)

- `TestStoreCommitsAreScopedPerCommand`: unlink, permanent delete, doctor
  `--fix` and the archive hook each keep a second task's pending edit out of
  their commit; the archive test also asserts the pushed store state is
  exactly the archive commit and nothing of the second task's.
- `test_concurrent_unlink_and_checkpoint_stay_scoped`: two processes produce
  exactly two commits, one per command, each scoped to its own task.
- `TestWholeStoreSweepsHoldTheStoreLock`: with the store lock held by the test,
  a command that triggers either sweep blocks until it is released, then
  completes (delete mark cleared / live record migrated to done/).
- All 7 new tests fail without the code change (verified by stashing it).

## Findings / debt

- A doctor repair that restores the exact committed state produces an empty
  commit (git sees nothing to stage). The scoping tests therefore give the
  repaired task an uncommitted edit of its own so the commit is non-empty.
- The store pushes to the parent repo (`store remote get-url origin`), not to
  the parent's remote, so the pushed state is read at
  `git -C <store remote> rev-parse tasks`.
- Pre-existing lint debt in this repo (not from this task): 25 ruff errors and
  67 files unformatted repo-wide, incl. `doctor.py:290` S110. No new ruff
  errors in the touched files; `ruff format --check` flags the same files
  before and after the change.
- `./hammer check all` and `check.py all` resolve to `/bin/true` stubs in the
  store config, so they pass vacuously; real gate is pytest + ruff.