#!/usr/bin/env python3
"""
check - Run validation and quality checks on the codebase
Usage: check <command> [options]

Commands:
  lint         - Run linter
  test         - Run tests
  typecheck    - Run type checker
  format       - Run formatter
  all          - Run all checks

Options:
  --fix        - Apply fixes where possible
  --json       - JSON output
"""

import argparse
import os
import subprocess
import sys
import yaml


def load_config(tasks_dir=".tasks"):
    config_path = os.path.join(tasks_dir, "config.yaml")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            return {}
    return {}


def get_tool(config, tool_type):
    key_map = {
        "lint": "repo.lint",
        "test": "repo.test",
        "typecheck": "repo.type_check",
        "format": "repo.format",
    }
    return config.get(key_map.get(tool_type))


def get_commands():
    return {
        "lint": {
            "ruff": ["ruff", "check", "."],
            "pylint": ["pylint", "."],
            "eslint": ["npx", "eslint", "."],
            "golangci-lint": ["golangci-lint", "run", "./..."],
        },
        "test": {
            "pytest": ["pytest"],
            "go test": ["go", "test", "./..."],
            "cargo test": ["cargo", "test"],
            "npm test": ["npm", "test"],
        },
        "typecheck": {
            "mypy": ["mypy", "."],
            "pyright": ["npx", "pyright", "."],
            "typescript": ["npx", "tsc", "--noEmit"],
        },
        "format": {
            "ruff": ["ruff", "format", "."],
            "prettier": ["npx", "prettier", "--write", "."],
            "rustfmt": ["cargo", "fmt"],
        },
    }


def run_check(tool_type, fix=False, as_json=False):
    config = load_config()
    tool = get_tool(config, tool_type)
    commands = get_commands().get(tool_type, {})

    if not tool or tool not in commands:
        if as_json:
            print(
                f'{{"tool": "{tool_type}", "error": "No {tool_type} tool configured", "configured": null}}'
            )
        else:
            print(
                f"No {tool_type} tool configured. Run 'python tasks.py config detect --save' to configure."
            )
        return 1

    cmd = commands[tool].copy()

    if tool_type == "format" and not fix:
        cmd.append("--check")
    elif tool_type == "lint" and fix:
        cmd.append("--fix")

    import shutil

    cmd0 = shutil.which(cmd[0])
    if not cmd0:
        venv_bin = os.path.join(os.getcwd(), "venv", "bin", cmd[0])
        if os.path.exists(venv_bin):
            cmd0 = venv_bin

    if not cmd0:
        if as_json:
            print(
                f'{{"tool": "{tool_type}", "error": "Tool not found in PATH", "configured": "{tool}"}}'
            )
        else:
            print(f"Tool '{cmd[0]}' not found in PATH.")
        return 1

    cmd[0] = cmd0

    if as_json:
        print(
            f'{{"tool": "{tool_type}", "command": {" ".join(cmd)}, "configured": "{tool}"}}'
        )
    else:
        print(f"Running {tool} ({tool_type})...")
        result = subprocess.run(cmd, cwd=os.getcwd(), capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return result.returncode


def run_all(fix=False, as_json=False):
    results = {}
    for check in ["lint", "test", "typecheck", "format"]:
        results[check] = run_check(check, fix, as_json)

    if not as_json:
        print("\n" + "=" * 40)
        all_passed = all(r == 0 for r in results.values())
        if all_passed:
            print("✅ All checks passed")
        else:
            print("❌ Some checks failed")
            for check, code in results.items():
                status = "✅" if code == 0 else "❌"
                print(f"  {status} {check}")

    return 0 if all(r == 0 for r in results.values()) else 1


def main():
    parser = argparse.ArgumentParser(
        prog="check",
        description="Run validation and quality checks on the codebase",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=["lint", "test", "typecheck", "format", "all"],
        help="Check to run",
    )
    parser.add_argument("--fix", action="store_true", help="Apply fixes where possible")
    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    if args.command == "all":
        return run_all(args.fix, args.json)
    else:
        return run_check(args.command, args.fix, args.json)


if __name__ == "__main__":
    sys.exit(main())
