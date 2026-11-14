#!/usr/bin/env python3
"""
check - Run validation and quality checks
Usage: check <command> [args]

Commands:
  lint         Run linter (exit 0 = pass, 1 = fail)
  test         Run test suite (exit 0 = pass, 1 = fail)
  typecheck    Run type checker (exit 0 = pass, 1 = fail)
  format       Run formatter check (exit 0 = pass, 1 = fail)
  debug        Check for debug messages (exit 0 = pass, 1 = fail)
  all          Run every check (exit 0 = pass, 1 = fail)

Examples:
  hammer check all
  hammer check lint
  hammer check lint --fix
  hammer check lint -h
"""

import argparse
import os
import subprocess
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tasks_ai.help_text import agent_epilog
from tasks_ai.validator import ValidationError, Validator, format_check_results

COMMAND_HELP = {
    "lint": "Run linter (exit 0 = pass, 1 = fail)",
    "test": "Run test suite (exit 0 = pass, 1 = fail)",
    "typecheck": "Run type checker (exit 0 = pass, 1 = fail)",
    "format": "Run formatter check (exit 0 = pass, 1 = fail)",
    "debug": "Check for debug messages (exit 0 = pass, 1 = fail)",
    "all": "Run every check (exit 0 = pass, 1 = fail)",
}


def project_root():
    """Resolve the project root (a worktree counts) so checks run in the right tree."""
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True
        ).strip()
    except Exception:  # noqa: BLE001
        return "."


def build_parser():
    parser = argparse.ArgumentParser(
        prog="check",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=agent_epilog("check"),
    )
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--fix", action="store_true", help="Apply fixes where possible."
    )
    common.add_argument(
        "--dev", action="store_true", help="Use /tmp/.tasks for config."
    )
    sub = parser.add_subparsers(dest="command", metavar="command")
    for name, help_text in COMMAND_HELP.items():
        sub.add_parser(
            name,
            parents=[common],
            help=help_text,
            description=f"check {name} - {help_text}",
        )
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    validator = Validator(project_root(), dev=args.dev)
    try:
        if args.command == "all":
            results = validator.run_all(args.fix)
        elif args.command == "debug":
            results = [validator.run_debug()]
        else:
            results = [validator.run_check(args.command, args.fix)]
    except ValidationError as e:
        print(
            format_check_results(
                [
                    {
                        "success": False,
                        "status": "blocker",
                        "tool": "validation",
                        "stdout": str(e),
                        "stderr": "",
                        "exit_code": 1,
                    }
                ]
            )
        )
        sys.exit(1)
    except Exception as e:  # noqa: BLE001
        print(f"Error: {e}")
        sys.exit(1)

    print(format_check_results(results))
    sys.exit(0 if all(r["success"] for r in results) else 1)


if __name__ == "__main__":
    main()
