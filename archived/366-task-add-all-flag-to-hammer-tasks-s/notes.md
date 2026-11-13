# 366 — tasks show --all

## Implementation (commit cc8f04ce on 366-task-add-...)
- tasks.py: show subparser gained `--all` (store_true); dispatch prefers it over the single-task and bare-list paths.
- tasks_ai/cli.py:867: show() forwards show_all to the command.
- tasks_ai/commands/show.py: `run_all(cli)` walks STATE_FOLDERS and emits one record per task dir: state, file, name, type, branch, metadata (KEY_MAP names) and `files` = every .md in the dir (parts filtered to real files, so verification_proof.log/.audit_hash never leak in). Text mode prints each record's md files; `-j` emits the record list as data.
- Single-task path untouched: `tasks show <id>` still prints current-task.md dump; `tasks show` (no args) still lists.

## Verification
- ./hammer check all: lint/test/typecheck/format green (runs against main-repo root; note gates test main, not the task branch — see task 342/343).
- Manual --dev: `tasks --dev show --all` text + `-j` JSON across BACKLOG/READY; `show <id> --all`; `show <id>` unchanged; `show --help` documents --all.
- tests/test_show_all.py added (4 user tests, HammerTestBase pattern like task 316). Same caveat as test_unlink.py: the fixture clones and checks out main, so these are green once this branch is merged to main, not before.

## Debt / notes
- The fixture harness testing main (not the branch) is a pre-existing pipeline gap; not addressed here.
