
- Progress:
  - Rewrote tasks_ai/check_wrapper.py with argparse subcommands
    (lint/test/typecheck/format/debug/all); each subcommand now runs only its own
    check and -h/--help print per-subcommand usage. Kept the
    "Results: [...]" output so tests/test_check_worktree.py still passes.
    Exit code is now 0/1 based on check results (it used to always be 0).
  - Converted repo.py main() to argparse (merge/promote/demote/sync/commit/git/
    status/check-merged/check-merged-testing/branch{list,create,delete,exists}).
    -h is no longer swallowed as a branch name ('repo merge main -h' used to try
    to resolve branch '-h'; 'repo demote 1 PROGRESSING -h' actually started a
    demotion). Global flags (-y/-q/-j/--dev) are accepted before or after the
    command via SUPPRESS defaults; repo.py now exits non-zero on failure.
  - hammer: COMMAND_TO_TOOL gains audit/verify/restore/unarchive/init-hooks;
    dropped the phantom run/help/-h/--help entries. A bare tool invocation now
    delegates to the tool, which prints its own usage and exits 1 (replaces
    "HAMMER DEMAND: Specify command for X"). tasks.py subparsers are no longer
    required so bare 'hammer tasks' prints help + exit 1.
  - Added tasks_ai/help_text.py agent_epilog() so check/repo/guard help (and the
    wrapper docstring) surface the agent contract (-j for JSON output,
    <tool> <command> -h).
  - New tests/test_help_coverage.py: audits every tool + subcommand with -h and
    --help in explicit and auto-detect form, tool layout/agent contract/no
    persona, bare invocation, and help never JSON-wrapped. Reads each tool's
    command list out of its own -h output, so a new subcommand is audited
    automatically. ~2 min on one core.

- Findings / debt:
  - Pre-existing suite failures (present on main, not touched here):
    tests/test_robustness.py (4 regression-check gate tests) and
    tests/test_repo.py::test_repo_save_with_mock_remote (save refused in --dev).
  - Pre-existing, out of scope: 'hammer repo commit <msg>' fails in a task
    worktree with "Command failed: git add ." because find_project_root() walks
    up past a worktree's .git *file* to the main repo. Verified with the
    unmodified repo.py from HEAD.
  - tasks/guard subcommand help does not repeat the AGENT_GUIDANCE epilog
    (only the tool-level help does). R4's example ("tasks keeps AGENT_GUIDANCE
    as its argparse epilog") is satisfied as-is.