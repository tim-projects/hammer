Audit ran every tool and subcommand with -h and --help (161 invocations). Findings: (1) tasks_ai/check_wrapper.py is a stub with zero argument parsing: 'hammer check <anything> -h' prints 'Validator imported' and runs all checks, ignoring both the flag and the subcommand. (2) repo.py parses sys.argv manually (repo.py:362-420): no -h/--help handling anywhere; -h is swallowed as a positional (e.g. 'repo merge main -h' fails with 'COULD NOT RESOLVE BRANCH: -h'). (3) hammer wrapper COMMAND_TO_TOOL (hammer:42-87) omits audit, restore, init-hooks, unarchive, verify, so auto-detect -h dies with 'Unknown tool or command'; phantom 'run'/'help' entries point at tasks subparsers that do not exist, producing argparse invalid-choice errors. (4) Bare 'hammer tasks/check/repo/guard' print 'HAMMER DEMAND: Specify command for X' (hammer:126-128) instead of usage. (5) 'hammer tasks undo' has a subparser (tasks.py:107-108) but no dispatch branch, so it silently no-ops. Full results: PASS=104, FAIL=57.

HELP MESSAGE RULES & FORMAT (guides: hammer:2-24; guard.py:2-12 and 271-314; tasks.py:10-15; tasks_ai/help_text.py; check.py:563-586; data/hints.json; tasks_ai/cli_io.py)

R1. Tool-level help layout, identical for every tool, both -h and --help:
  Line 1: '<tool> - <one-line purpose>'
  Line 2: 'Usage: <tool> <command> [args]'
  then a 'Commands:' block: two-space indent, one command per line, descriptions aligned in a single column, each entry annotated with exit codes and side effects (guard.py model: '(exit 0 = pass, 1 = reject)', '(read-only)').
  then an 'Examples:' block of copy-pasteable invocations. The wrapper additionally keeps its 'Tools:' block and shows both explicit-tool and auto-detected examples.
  Positionals written <arg>, optionals [--flag].

R2. Subcommand help layout:
  Use argparse with the default add_help=True so -h and --help come free; never hand-parse sys.argv.
  Pass description=__doc__ so the docstring and help stay in sync (guard.py:271-272 pattern); the usage line must list every positional and optional.
  Every positional and flag carries a help= string; defaults and choices documented.
  No command supplied -> parser.print_help() then exit 1 (guard.py:312-314, check.py:581-583). Bad arguments -> parser.error() (argparse exits 2).

R3. Global flags identical across all tools: -j/--json, -q/--quiet, --dev (isolated /tmp/.tasks), -y/--yes on destructive commands; --version only on tasks.

R4. Agent contract: every help response must surface the rules in tasks_ai/help_text.py (AGENT_GUIDANCE) - '-j for JSON output (machine-parseable for agents)' and 'tasks <command> -h' for per-command help. tasks keeps AGENT_GUIDANCE as its argparse epilog.

R5. Tone: help text is plain and factual - no emoji, no hammer persona. Persona is reserved for failures: the wrapper prints '❌ HAMMER SAY NO! {msg} 🔨' (hammer:89-91); tasks_ai prints 'Error: {message} | HINT: {hint}' to stderr and exits 1 (tasks_ai/cli_io.py). Hints follow the WHAT/WHY/HOW/CONSEQUENCE template in data/hints.json and must name the exact next command.

R6. JSON mode never wraps help: help always prints plain text to stdout and exits 0, even with -j. The {'success','messages','data'} envelope is for command results only.

R7. Wrap at 80 columns: use argparse.RawDescriptionHelpFormatter for custom layouts (tasks.py:10); hand-written docstrings (guard.py, hammer) wrap at that width.

R8. Both invocation styles must work for every response: 'hammer <tool> <cmd> -h' and 'hammer <cmd> -h' (auto-detect), each for -h and --help, exit 0.