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
import json
import shutil
import tempfile
from pathlib import Path


def get_git_root():
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"], stderr=subprocess.DEVNULL
            )
            .decode()
            .strip()
        )
    except Exception:
        return os.getcwd()


def find_project_root(start_path=None):
    """Search upward for .tasks directory or .git directory."""
    if start_path is None:
        # Start from cwd first to respect test isolation and invocation context
        start_path = os.getcwd()

    current = os.path.abspath(start_path)
    while True:
        if os.path.isdir(os.path.join(current, ".tasks")) or os.path.isdir(
            os.path.join(current, ".git")
        ):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent

    # Fallback to script location
    return Path(__file__).parent.resolve()


ROOT = find_project_root()


def load_config(dev=False):
    project_root = find_project_root()
    # Prioritize project_root/.tasks/config.yaml (or /tmp/.tasks/config.yaml if dev), then project_root/pyproject.toml
    if dev:
        config_path_yaml = "/tmp/.tasks/config.yaml"
    else:
        config_path_yaml = os.path.join(project_root, ".tasks", "config.yaml")

    config_path_toml = os.path.join(project_root, "pyproject.toml")

    config = {}
    if os.path.exists(config_path_yaml):
        try:
            import yaml

            with open(config_path_yaml, "r") as f:
                config.update(yaml.safe_load(f) or {})
        except ImportError:
            print(
                "Warning: 'PyYAML' library not found. Skipping config.yaml parsing.",
                file=sys.stderr,
            )
        except Exception as e:
            print(f"Warning: Could not parse {config_path_yaml}: {e}", file=sys.stderr)

    if os.path.exists(config_path_toml):
        try:
            import toml

            with open(config_path_toml, "r") as f:
                pyproject_data = toml.load(f)
                config_section = (
                    pyproject_data.get("tool", {}).get("tasks_ai", {}).get("repo", {})
                )
                config.update(config_section)
        except ImportError:
            pass
        except Exception as e:
            print(f"Warning: Could not parse pyproject.toml: {e}", file=sys.stderr)

    return config


def get_tool(config, tool_type):
    # Standardize on repo.<tool_type>
    # Special case: TasksCLI uses repo.type_check
    key_map = {
        "lint": "repo.lint",
        "test": "repo.test",
        "typecheck": "repo.type_check",
        "format": "repo.format",
    }
    return config.get(key_map.get(tool_type))


def get_commands(fix=False):
    return {
        "lint": {
            "ruff": ["ruff", "check", "."] + (["--fix"] if fix else []),
            "pylint": ["pylint", "."],
            "eslint": ["npx", "eslint", "."] + (["--fix"] if fix else []),
            "golangci-lint": ["golangci-lint", "run", "./..."]
            + (["--fix"] if fix else []),
        },
        "test": {
            "pytest": ["pytest"],
            "go test": ["go", "test", "./..."],
            "cargo test": ["cargo", "test"],
            "npm test": ["npm", "test"],
        },
        "typecheck": {
            "mypy": ["mypy", "."],
            "pyright": ["npx", "pyright"],
            "typescript": ["npx", "tsc", "--noEmit"],
        },
        "format": {
            "ruff": ["ruff", "format", "."] + (["--check"] if not fix else []),
            "prettier": ["npx", "prettier", "--write", "."]
            if fix
            else ["npx", "prettier", "--check", "."],
            "rustfmt": ["cargo", "fmt"] + (["--check"] if not fix else []),
        },
    }


def run_check(tool_type, fix=False, as_json=False, dev=False):
    sys.stderr.flush()
    config = load_config(dev)
    sys.stderr.flush()

    # Standardize tool type to config key mapping
    key_map = {
        "lint": "repo.lint",
        "test": "repo.test",
        "typecheck": "repo.type_check",
        "format": "repo.format",
    }
    config_key = key_map.get(tool_type)
    tool = config.get(config_key)
    sys.stderr.flush()

    commands = get_commands(fix).get(tool_type, {})
    sys.stderr.flush()

    if not tool or tool not in commands:
        # Try auto-detecting once if tool is missing
        project_root = find_project_root()
        tasks_py = os.path.join(project_root, "tasks.py")
        if os.path.exists(tasks_py):
            if not as_json:
                print(
                    f"⚠️ NO {tool_type.upper()} CONFIGURED! ATTEMPTING AUTO-DETECTION... 🔨"
                )

            subprocess.run(
                [sys.executable, tasks_py, "config", "detect", "--save"],
                cwd=project_root,
                capture_output=True,
                text=True,
            )
            # Reload config and try again
            config = load_config(dev)
            tool = config.get(config_key)

    if not tool or tool not in commands:
        msg = f"❌ NO {tool_type} TOOL CONFIGURED! (EXPECTED KEY: {config_key})! RUN 'tasks config detect' OR SET MANUALLY: tasks config set {config_key} <tool>! 🔨"
        if as_json:
            print(
                json.dumps(
                    {
                        "success": False,
                        "tool": tool_type,
                        "error": msg,
                        "configured": tool,
                    }
                )
            )
        else:
            print(f"❌ HAMMER SAY NO! {msg}")
        return 1

    cmd = commands[tool].copy()

    # Path discovery
    project_root = find_project_root()
    cmd0 = shutil.which(cmd[0])
    if not cmd0:
        venv_bin = os.path.join(project_root, "venv", "bin", cmd[0])
        if os.path.exists(venv_bin):
            cmd0 = venv_bin

    if not cmd0:
        msg = f"❌ TOOL '{cmd[0]}' NOT FOUND IN PATH! INSTALL IT OR CHECK CONFIGURATION! 🔨"
        if as_json:
            print(
                json.dumps(
                    {
                        "success": False,
                        "tool": tool_type,
                        "error": msg,
                        "configured": tool,
                    }
                )
            )
        else:
            print(f"❌ HAMMER SAY NO! {msg}")
        return 1

    cmd[0] = cmd0

    # Run pytest with explicit path to project root to avoid test discovery issues
    cmd_to_run = cmd.copy()
    if tool == "pytest":
        # Add explicit path to the project root to ensure pytest finds tests
        # Also disable test collection caching to avoid issues
        cmd_to_run.append(project_root)
        cmd_to_run.extend(["--cache-clear", "-x"])  # Clear cache, stop on first failure

    # Execute the command
    if not as_json:
        print(f"Running {tool} ({tool_type})...")

    try:
        if as_json:
            # Capture output using temporary files to avoid pipe deadlocks
            with (
                tempfile.NamedTemporaryFile(mode="w+b", delete=False) as stdout_file,
                tempfile.NamedTemporaryFile(mode="w+b", delete=False) as stderr_file,
            ):
                result = subprocess.run(
                    print(cmd),
                    cmd_to_run,
                    cwd=project_root,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    timeout=300,
                )
                stdout_file.seek(0)
                stderr_file.seek(0)
                stdout_content = stdout_file.read().decode("utf-8", errors="replace")
                stderr_content = stderr_file.read().decode("utf-8", errors="replace")
            # Cleanup temp files
            try:
                os.unlink(stdout_file.name)
                os.unlink(stderr_file.name)
            except Exception:
                pass
        else:
            # Stream output directly to console to avoid deadlocks
            result = subprocess.run(cmd_to_run, cwd=project_root, timeout=300)
            stdout_content = ""
            stderr_content = ""
    except subprocess.TimeoutExpired:
        msg = f"❌ TOOL '{tool}' TIMED OUT AFTER 5 MINUTES! 🔨"
        if as_json:
            print(
                json.dumps(
                    {
                        "success": False,
                        "tool": tool_type,
                        "error": msg,
                        "configured": tool,
                    }
                )
            )
        else:
            print(f"Error: {msg}")
        return 1

    # Attach captured output to result for unified handling
    result.stdout = stdout_content
    result.stderr = stderr_content

    if as_json:
        print(
            json.dumps(
                {
                    "success": result.returncode == 0,
                    "tool": tool_type,
                    "configured": tool,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "exit_code": result.returncode,
                }
            )
        )
    else:
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        if result.returncode == 0:
            print(f"✅ HAMMER LIKE! {tool} PASSED! ⚔️🔨")
        else:
            print(f"❌ HAMMER SAY NO! {tool} FAILED! 🔨")
            print(
                "\n⚠️ HAMMER NO BYPASS TOOL - FIX ACTUAL CODE ISSUES, NOT VALIDATION CONFIG!"
            )
            print("   SEE AGENTS.md - NEVER SKIP OR BYPASS SECTION!")

    return result.returncode


def get_current_hash():
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
            )
            .decode()
            .strip()
        )
    except Exception:
        return None


def get_last_hash_path():
    return os.path.join(find_project_root(), ".tasks", ".last_validation_hash")


def run_all(fix=False, as_json=False, dev=False):
    current_hash = get_current_hash()
    hash_path = get_last_hash_path()

    if not fix and current_hash and os.path.exists(hash_path):
        with open(hash_path, "r") as f:
            last_hash = f.read().strip()
        if last_hash == current_hash:
            if not as_json:
                print("✅ CODE UNCHANGED! HAMMER SKIP VALIDATION! ⚔️🔨")
            return 0

    results = {}
    total_code = 0
    for check in ["lint", "test", "typecheck", "format"]:
        code = run_check(check, fix, as_json, dev)
        results[check] = code
        if code != 0:
            total_code = 1

    if total_code == 0 and current_hash:
        with open(hash_path, "w") as f:
            f.write(current_hash)

    if not as_json:
        print("\n" + "=" * 40)
        all_passed = total_code == 0
        if all_passed:
            print("✅ HAMMER LIKE! ALL CHECKS PASSED! ⚔️🔨")
        else:
            print("❌ HAMMER SAY NO! SOME CHECKS FAILED! 🔨")
            for check, code in results.items():
                status = "✅" if code == 0 else "❌"
                print(f"  {status} {check}")
            print(
                "\n⚠️ HAMMER IMPORTANT: DO NOT MODIFY VALIDATION CONFIG OR DISABLE CHECKS TO HIDE ERRORS!"
            )
            print("   SEE AGENTS.md - NEVER SKIP OR BYPASS SECTION!")
            print("   FIX ACTUAL CODE ISSUES, NOT VALIDATION TOOL!")

    return total_code


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
    parser.add_argument("--dev", action="store_true", help="Use /tmp/.tasks for config")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "all":
        return run_all(args.fix, args.json, args.dev)
    else:
        return run_check(args.command, args.fix, args.json, args.dev)


if __name__ == "__main__":
    sys.exit(main())
