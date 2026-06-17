import os
import json
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
        from .validator import Validator, ValidationError

        root = self.cli.context.repo_root or os.getcwd()
        validator = Validator(root, dev=self.cli.dev)

        try:
            if tool_name and tool_name != "all":
                result = validator.run_check(tool_name, fix)
                results = [result]
            else:
                results = validator.run_all(fix)

            success = all(r["success"] for r in results)

            if self.cli.as_json:
                data = {"success": success, "results": results}
                if success:
                    self.cli.finish(data)
                else:
                    self.cli.error("Validation failed", hint=json.dumps(results))
            else:
                for r in results:
                    print(r.get("stdout", ""))

                if success:
                    print("✅ Validation passed")
                else:
                    print("❌ Validation failed")
                    self.cli.error("Pipeline validation failed.")

        except ValidationError as e:
            self.cli.error(str(e))
