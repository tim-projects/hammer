import os
import sys
import subprocess
import json
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from .cli_engine import TasksCLI


class Validation:
    def __init__(self, cli: "TasksCLI"):
        self.cli = cli

    def run_lint(self, fix=False):
        if os.environ.get("TASKS_TESTING") == "1":
            return
        check_path = os.path.join(self.cli.root, "check.py")
        if not os.path.exists(check_path):
            return
        result = subprocess.run(
            [sys.executable, check_path, "lint"] + (["--fix"] if fix else []),
            cwd=self.cli.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            self.cli.error(
                "❌ HAMMER SAY NO! VALIDATION BROKEN! FIX NOW! 🔨",
                hint="RUN 'check lint' TO SEE ERRORS. HAMMER NO BYPASS TOOL!",
            )

    def run_tests(self, fail_safe=False):
        if os.environ.get("TASKS_TESTING") == "1":
            return subprocess.CompletedProcess("", 0)
        check_path = os.path.join(self.cli.root, "check.py")
        if not os.path.exists(check_path):
            return subprocess.CompletedProcess("", 0)
        result = subprocess.run(
            [sys.executable, check_path, "test"],
            cwd=self.cli.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            if fail_safe:
                return result
            self.cli.error(
                "❌ TEST BREAK! HAMMER SAY NO! FIX NOW! 🔨",
                hint="RUN 'check test' TO SEE FAILURES. HAMMER NO BYPASS TOOL!",
            )
        return result

    def detect_tools(self) -> Dict[str, str]:
        """Detect project type and suggest/create config."""
        detected = {}
        root = self.cli.root

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
        check_py = os.path.join(self.cli.root, "check.py")
        if not os.path.exists(check_py):
            self.cli.error("check.py not found in project root.")
            return

        cmd = [sys.executable, check_py, tool_name or "all"]
        if fix:
            cmd.append("--fix")
        if self.cli.as_json:
            cmd.append("--json")

        result = subprocess.run(cmd, cwd=self.cli.root, capture_output=True, text=True)

        if self.cli.as_json:
            try:
                data = json.loads(result.stdout)
                if result.returncode == 0:
                    self.cli.finish(data)
                else:
                    self.cli.error(
                        f"Tool execution failed: {tool_name}", hint=data.get("error")
                    )
            except json.JSONDecodeError:
                self.cli.error(f"Failed to parse tool output: {result.stdout}")
        else:
            print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            if result.returncode != 0:
                self.cli.error(f"Tool execution failed: {tool_name}")
