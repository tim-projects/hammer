import subprocess
import shutil
import os
from pathlib import Path
from typing import List, Dict


class ValidationError(Exception):
    """Exception raised for validation errors."""

    pass


class Validator:
    def __init__(self, project_root: str, dev: bool = False):
        self.project_root = Path(project_root).resolve()
        self.dev = dev
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """Load configuration from .tasks/config.yaml or pyproject.toml."""
        config_path_yaml = (
            Path(os.environ.get("HAMMER_DEV_TASKS_DIR", "/tmp/.tasks")) / "config.yaml"
            if self.dev
            else (self.project_root / ".tasks" / "config.yaml")
        )
        config_path_toml = self.project_root / "pyproject.toml"

        config = {}
        # Parse YAML
        if config_path_yaml.exists():
            try:
                import yaml

                with open(config_path_yaml, "r") as f:
                    config.update(yaml.safe_load(f) or {})
            except ImportError:
                pass

        # Parse TOML
        if config_path_toml.exists():
            try:
                import toml

                with open(config_path_toml, "r") as f:
                    pyproject_data = toml.load(f)
                    config_section = (
                        pyproject_data.get("tool", {})
                        .get("tasks_ai", {})
                        .get("repo", {})
                    )
                    config.update(config_section)
            except ImportError:
                pass
        return config

    def _get_commands(self, fix: bool) -> Dict:
        """Returns the full set of supported commands."""
        return {
            "lint": {
                "ruff": ["ruff", "check", "."] + (["--fix"] if fix else []),
                "pylint": ["pylint", "."],
                "eslint": ["npx", "eslint", "."] + (["--fix"] if fix else []),
                "golangci-lint": ["golangci-lint", "run", "./..."]
                + (["--fix"] if fix else []),
                "true": ["/bin/true"],
            },
            "test": {
                "pytest": ["pytest"],
                "go test": ["go", "test", "./..."],
                "cargo test": ["cargo", "test"],
                "npm test": ["npm", "test"],
                "true": ["/bin/true"],
            },
            "typecheck": {
                "mypy": ["mypy", "."],
                "pyright": ["npx", "pyright"],
                "typescript": ["npx", "tsc", "--noEmit"],
                "true": ["/bin/true"],
            },
            "format": {
                "ruff": ["ruff", "format", "."] + (["--check"] if not fix else []),
                "prettier": ["npx", "prettier", "--write", "."]
                if fix
                else ["npx", "prettier", "--check", "."],
                "rustfmt": ["cargo", "fmt"] + (["--check"] if not fix else []),
                "true": ["/bin/true"],
            },
        }

    def run_check(self, tool_type: str, fix: bool = False, timeout: int = 60) -> Dict:
        """Run a specific validation tool."""
        commands = self._get_commands(fix)
        tool_config_key = {
            "lint": "repo.lint",
            "test": "repo.test",
            "typecheck": "repo.type_check",
            "format": "repo.format",
        }.get(tool_type)

        # Handle both nested and flat config formats
        tool = self.config.get(tool_config_key)
        if tool is None:
            tool = self.config.get("repo", {}).get(tool_config_key.replace("repo.", ""))

        # Normalize tool name (handle /bin/true style paths)
        if tool and tool.startswith("/bin/"):
            tool = "true"

        # Look up the actual command list for this tool
        cmd_list = commands.get(tool_type, {}).get(tool)
        if not cmd_list:
            raise ValidationError(
                f"Tool '{tool_type}' ({tool}) not configured or not supported."
            )

        cmd = cmd_list.copy()

        # Path resolution
        cmd0 = shutil.which(cmd[0])
        if not cmd0:
            venv_bin = self.project_root / "venv" / "bin" / cmd[0]
            if venv_bin.exists():
                cmd0 = str(venv_bin)

        if not cmd0:
            raise ValidationError(f"Tool '{cmd[0]}' not found in PATH or venv.")

        cmd[0] = cmd0

        # Suppress npm/npx interactive prompts and update notifiers in CI/automated contexts
        run_env = os.environ.copy()
        run_env["NPM_CONFIG_UPDATE_NOTIFIER"] = "false"
        run_env["CI"] = "true"

        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                env=run_env,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise ValidationError(f"Tool '{tool}' timed out after {timeout} seconds.")

        return {
            "success": result.returncode == 0,
            "tool": tool_type,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }

    def run_all(self, fix: bool = False, force: bool = False) -> List[Dict]:
        """Run all configured checks with caching."""
        if not force and not fix and self._is_unchanged():
            return [
                {
                    "success": True,
                    "tool": "all",
                    "stdout": "Codebase unchanged, skipping validation.",
                    "exit_code": 0,
                }
            ]

        results = []
        for tool in ["lint", "test", "typecheck", "format"]:
            results.append(self.run_check(tool, fix))

        if all(r["success"] for r in results):
            self._update_hash()

        return results

    def _is_unchanged(self) -> bool:
        """Check if codebase has changed since last validation."""
        hash_path = self.project_root / ".tasks" / ".last_validation_hash"
        if not hash_path.exists():
            return False

        current_hash = self._get_git_hash()
        with open(hash_path, "r") as f:
            return f.read().strip() == current_hash

    def _get_git_hash(self) -> str:
        try:
            return (
                subprocess.check_output(
                    ["git", "rev-parse", "HEAD"],
                    cwd=self.project_root,
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
        except Exception:
            return ""

    def _update_hash(self):
        hash_path = self.project_root / ".tasks" / ".last_validation_hash"
        hash_path.parent.mkdir(exist_ok=True)
        with open(hash_path, "w") as f:
            f.write(self._get_git_hash())

    def run_debug(self) -> Dict:
        """Run debug messages check."""
        script_path = (
            self.project_root / "scripts" / "staging-remove-debug-messages-check.sh"
        )
        if not script_path.exists():
            raise ValidationError(f"Debug check script not found at {script_path}")

        result = subprocess.run(
            [str(script_path)], cwd=self.project_root, capture_output=True, text=True
        )
        return {
            "success": result.returncode == 0,
            "tool": "debug",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
