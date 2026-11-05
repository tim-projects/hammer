---
Task: 316-task-implement-tasks-unlink-subcomm
---

# Progress notes

## Implementation (branch 316)

- New `tasks_ai/commands/unlink.py` mirrors `commands/link.py` with inverse
  `Bl` semantics: resolve both tasks (LINK_TASK_NOT_FOUND / LINK_SELF reuse),
  remove the blocker filename from the `Bl` metadata list, `_atomic_write`,
  append an `Unlk` progress-log entry, and commit to the `.tasks` worktree
  with message `Unlk <file>-><blocker>`.
- Not-linked pair is a no-op: logs `Not linked: ...`, exits 0 with
  `data.changed = False` (no metadata write, no commit).
- Registered: `TasksCLI.unlink` delegation (`tasks_ai/cli.py`), subparser +
  dispatch in `tasks.py`, and `"unlink": "tasks"` in `hammer`
  COMMAND_TO_TOOL so `hammer unlink <a> <b>` auto-detects the tasks tool.
- User tests: `tests/test_unlink.py` (HammerTestBase + `--dev` storage, files
  copied into fixture like `test_guard.py` does). 6 tests: help visibility,
  link->unlink roundtrip, unlink-without-link no-op, double unlink, unknown
  blocker, self-unlink. All pass.

## Validation

- ruff check/format clean on all changed files.
- `python3 check.py all --force` passes (project config sets lint/test/
  typecheck/format to /bin/true — pre-existing choice, untouched).

## Notes / debt

- PRE-EXISTING ruff findings in `hammer` (I001, F401, PLW1510 at lines 26/28/
  131) exist on main and are unrelated to this change — not touched here.
  Tracked for a follow-up task since AGENTS.md requires a task for
  pre-existing errors before merge-to-main.
- Fixture harness (HammerTestBase) checks out `main`, so new tests must copy
  branch-only files into the fixture — see `_install_unlink_into_fixture`.
