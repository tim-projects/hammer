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

def get_git_root():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return os.getcwd()

ROOT = get_git_root()

def load_config():
    # Prioritize ROOT/.tasks/config.yaml, then ROOT/pyproject.toml
    config_path_yaml = os.path.join(ROOT, ".tasks", "config.yaml")
    config_path_toml = os.path.join(ROOT, "pyproject.toml")

    config = {}
    if os.path.exists(config_path_yaml):
        try:
            import yaml
            with open(config_path_yaml, "r") as f:
                config.update(yaml.safe_load(f) or {})
        except ImportError:
            print("Warning: 'PyYAML' library not found. Skipping config.yaml parsing.", file=sys.stderr)
        except Exception as e:
            print(f"Warning: Could not parse {config_path_yaml}: {e}", file=sys.stderr)

    if os.path.exists(config_path_toml):
        try:
            import toml
            with open(config_path_toml, "r") as f:
                pyproject_data = toml.load(f)
                config_section = pyproject_data.get("tool", {}).get("tasks_ai", {}).get("repo", {})
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
            "golangci-lint": ["golangci-lint", "run", "./..."] + (["--fix"] if fix else []),
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
            "ruff": ["ruff", "format", "."] + (["--check"] if not fix else []),
            "prettier": ["npx", "prettier", "--write", "."] if fix else ["npx", "prettier", "--check", "."],
            "rustfmt": ["cargo", "fmt"] + (["--check"] if not fix else []),
        },
    }

def run_check(tool_type, fix=False, as_json=False):
    config = load_config()
    
    # Standardize tool type to config key mapping
    key_map = {
        "lint": "repo.lint",
        "test": "repo.test",
        "typecheck": "repo.type_check",
        "format": "repo.format",
    }
    config_key = key_map.get(tool_type)
    tool = config.get(config_key)

    commands = get_commands(fix).get(tool_type, {})

    if not tool or tool not in commands:
        msg = f"No {tool_type} tool configured (expected key: {config_key}). Run 'tasks config detect' or set manually: tasks config set {config_key} <tool>"
        if as_json:
            print(json.dumps({"success": False, "tool": tool_type, "error": msg, "configured": tool}))
        else:
            print(f"Error: {msg}")
        return 1
        msg = f"No {tool_type} tool configured. Run 'tasks config detect' or set manually: tasks config set repo.{tool_type} <tool>"
        if as_json:
            print(json.dumps({"success": False, "tool": tool_type, "error": msg, "configured": tool}))
        else:
            print(f"Error: {msg}")
        return 1

    cmd = commands[tool].copy()

    # Path discovery
    cmd0 = shutil.which(cmd[0])
    if not cmd0:
        venv_bin = os.path.join(ROOT, "venv", "bin", cmd[0])
        if os.path.exists(venv_bin):
            cmd0 = venv_bin

    if not cmd0:
        msg = f"Tool '{cmd[0]}' not found in PATH. Install it or check configuration."
        if as_json:
            print(json.dumps({"success": False, "tool": tool_type, "error": msg, "configured": tool}))
        else:
            print(f"Error: {msg}")
        return 1

    cmd[0] = cmd0

    if as_json:
        # In JSON mode, we just return the command that would be run? 
        # No, we should probably run it if we want 'check' to actually check.
        pass

    if not as_json:
        print(f"Running {tool} ({tool_type})...")
    
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    
    if as_json:
        print(json.dumps({
            "success": result.returncode == 0,
            "tool": tool_type,
            "configured": tool,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode
        }))
    else:
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        
        if result.returncode == 0:
            print(f"✅ {tool} passed")
        else:
            print(f"❌ {tool} failed")
            
    return result.returncode

def run_all(fix=False, as_json=False):
    results = {}
    total_code = 0
    for check in ["lint", "test", "typecheck", "format"]:
        code = run_check(check, fix, as_json)
        results[check] = code
        if code != 0:
            total_code = 1

    if not as_json:
        print("\n" + "=" * 40)
        all_passed = (total_code == 0)
        if all_passed:
            print("✅ All checks passed")
        else:
            print("❌ Some checks failed")
            for check, code in results.items():
                status = "✅" if code == 0 else "❌"
                print(f"  {status} {check}")

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

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "all":
        return run_all(args.fix, args.json)
    else:
        return run_check(args.command, args.fix, args.json)

if __name__ == "__main__":
    sys.exit(main())
