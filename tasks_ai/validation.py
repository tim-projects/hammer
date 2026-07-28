import os
import sys
import subprocess
import json
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from .cli_engine import TasksCLI


class Validation:
    def __init__(self, cli: "TasksCLI"):
        self.cli = cli

    def detect_tools(self) -> Dict[str, str]:
        """Detect project type and suggest/create config."""
        detected = {}
        # Ensure we use the actual repo root
        root = self.cli.context.repo_root or self.cli.root

        if os.path.exists(os.path.join(root, "package.json")):
            detected["package_manager"] = "npm"
            if os.path.exists(os.path.join(root, "yarn.lock")):
                detected["package_manager"] = "yarn"
            elif os.path.exists(os.path.join(root, "pnpm-lock.yaml")):
                detected["package_manager"] = "pnpm"

        if os.path.exists(os.path.join(root, "pyproject.toml")) or os.path.exists(
            os.path.join(root, "requirements.txt")
        ):
            detected["package_manager"] = "pip"
        elif os.path.exists(os.path.join(root, "Pipfile")):
            detected["package_manager"] = "pipenv"

        if os.path.exists(os.path.join(root, "go.mod")):
            detected["language"] = "go"
        if os.path.exists(os.path.join(root, "Cargo.toml")):
            detected["language"] = "rust"

        lint_files = {
            "ruff.toml": "ruff",
            "pyproject.toml": "ruff",
            ".eslintrc.js": "eslint",
            ".eslintrc.json": "eslint",
            "eslint.config.js": "eslint",
            "tsconfig.json": "typescript",
            ".golangci.yml": "golangci-lint",
            "pylintrc": "pylint",
        }
        for file, tool in lint_files.items():
            if os.path.exists(os.path.join(root, file)):
                detected["lint"] = tool
                break

        type_check_files = {
            "mypy.ini": "mypy",
            "pyrightconfig.json": "pyright",
            "tsconfig.json": "typescript",
        }
        for file, tool in type_check_files.items():
            if os.path.exists(os.path.join(root, file)):
                detected["type_check"] = tool
                break

        if os.path.exists(os.path.join(root, "pytest.ini")) or os.path.exists(
            os.path.join(root, "pyproject.toml")
        ):
            detected["test"] = "pytest"

        format_files = {
            "ruff.toml": "ruff",
            ".prettierrc": "prettier",
        }
        for file, tool in format_files.items():
            if os.path.exists(os.path.join(root, file)):
                detected["format"] = tool
                break

        return detected

    def validate_path(self, path: str) -> bool:
        """Ensure path is safe and within repo or a temporary testing directory."""
        abs_path = os.path.abspath(path)
        is_dev = self.cli.dev
        is_testing = os.environ.get("TASKS_TESTING") == "1"
        starts_tmp = path.startswith("/tmp")

        if is_dev or is_testing or starts_tmp:
            return True

        # Allow paths within the repo
        if abs_path.startswith(os.path.abspath(self.cli.root)):
            return True

        self.cli.error(f"Path outside repository: {path}")
        return False

    def run_tool(self, tool_name: Optional[str] = None, fix: bool = False):
        """Run configured tools (lint, test, typecheck, format)."""
        # Resolve project root independently of CWD using the same logic as repo_script
        install_dir = Path(__file__).resolve().parent.parent
        check_py = install_dir / "check.py"

        if not check_py.exists():
            self.cli.error("check.py not found in project root.")
            return

        cmd = [sys.executable, str(check_py), tool_name or "all"]
        if fix:
            cmd.append("--fix")
        if self.cli.as_json:
            cmd.append("--json")
        if self.cli.dev:
            cmd.append("--dev")

        # repo_root is still needed for execution context
        repo_root = self.cli.context.repo_root or os.getcwd()
        capture = True
        run_env = os.environ.copy()
        run_env["HAMMER_DEV_TASKS_DIR"] = self.cli.context.tasks_path or "/tmp/.tasks"
        result = subprocess.run(cmd, cwd=repo_root, capture_output=capture, text=True, env=run_env)

        if self.cli.as_json:
            try:
                # Handle potential JSON Lines (multiple JSON objects)
                lines = [
                    json.loads(line)
                    for line in result.stdout.strip().splitlines()
                    if line.strip()
                ]
                if len(lines) == 1:
                    data = lines[0]
                else:
                    # Aggregate results
                    data = {
                        "success": all(line.get("success", False) for line in lines),
                        "results": lines,
                    }

                if result.returncode == 0:
                    self.cli.finish(data)
                else:
                    # Try to extract a meaningful error
                    error_msg = "Tool execution failed"
                    for line in lines:
                        if not line.get("success", True):
                            error_msg = line.get("error", error_msg)
                            break
                    self.cli.error(
                        f"Tool execution failed: {tool_name or 'all'}", hint=error_msg
                    )
            except json.JSONDecodeError:
                self.cli.error(f"Failed to parse tool output: {result.stdout}")
        else:
            if result.stdout:
                print(result.stdout, file=sys.stderr)
            if result.stderr:
                print(result.stderr, file=sys.stderr)

            if result.returncode != 0:
                self.cli.error(f"Tool execution failed: {tool_name or 'all'}")
        return result
