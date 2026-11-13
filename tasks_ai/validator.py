import os
import shutil
import subprocess
from pathlib import Path


class ValidationError(Exception):
    """Exception raised for validation errors."""


# The list the promotion gate runs (check.py). 'hammer check' must run the same
# one: a bare 'pytest' collects the whole tree (~909s) and blows the 300s
# timeout, so the user-facing check could never go green.
PINNED_PYTEST_ARGS = [
    "tests/test_cli_robustness.py",
    "tests/test_repo.py",
    "tests/test_security.py",
    "tests/test_dev_mode.py",
    "tests/test_error_reporting.py",
    "tests/test_git_hook_restrictions.py",
    "tests/test_init_backup.py",
    "tests/test_pairing.py",
    # The pipeline suites exercise the move/gate hooks (and the research
    # gate) for real, so they are listed explicitly, never ignored. A suite
    # that cannot pass here gets its own fix task before check stays green.
    "tests/test_tasks.py",
    "tests/test_robustness.py",
    "tests/test_robustness_bugfix.py",
    "tests/test_all_transitions.py",
    "tests/test_artifact_healing.py",
    "tests/test_audit_verify.py",
    "tests/test_audit_verify_integration.py",
    "tests/test_cli_endpoints.py",
    "tests/test_tasks_modular.py",
]


class Validator:
    def __init__(self, project_root: str, dev: bool = False):
        self.project_root = Path(project_root).resolve()
        self.dev = dev
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """Load configuration from .tasks/config.yaml or pyproject.toml."""
        config_path_yaml = (
            Path(os.environ.get("HAMMER_DEV_TASKS_DIR", "/tmp/.tasks")) / "config.yaml"
            if self.dev
            else (self.project_root / ".tasks" / "config.yaml")
        )
        if not config_path_yaml.exists() and not self.dev:
            # A worktree has no .tasks of its own; the store config lives in the main repo
            config_path_yaml = self._store_config_path()
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

    def _store_config_path(self) -> Path:
        """Locate the store config from a worktree (the store is shared, in the main repo)."""
        try:
            common_dir = (
                subprocess.check_output(
                    ["git", "rev-parse", "--git-common-dir"],
                    cwd=self.project_root,
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
        except Exception:  # noqa: BLE001
            return self.project_root / ".tasks" / "config.yaml"
        if not os.path.isabs(common_dir):
            common_dir = os.path.join(self.project_root, common_dir)
        return Path(os.path.dirname(common_dir)) / ".tasks" / "config.yaml"

    @staticmethod
    def _is_noop_tool(tool) -> bool:
        """A configured no-op (true, /bin/true) skips the check, so it must fail."""
        if not tool:
            return False
        # YAML parses a bare `true` into the boolean, so compare case-insensitively.
        text = str(tool).strip().lower()
        return text == "true" or os.path.basename(text) == "true"

    def _get_commands(self, fix: bool) -> dict:
        """Returns the full set of supported commands."""
        return {
            "lint": {
                "ruff": ["ruff", "check", "."] + (["--fix"] if fix else []),
                "pylint": ["pylint", "."],
                "eslint": ["npx", "eslint", "."] + (["--fix"] if fix else []),
                "oxlint": ["npx", "oxlint", "."] + (["--fix"] if fix else []),
                "golangci-lint": ["golangci-lint", "run", "./..."]
                + (["--fix"] if fix else []),
                "noop": ["/bin/true"],
            },
            "test": {
                "pytest": ["pytest"] + PINNED_PYTEST_ARGS,
                "go test": ["go", "test", "./..."],
                "cargo test": ["cargo", "test"],
                "npm test": ["npm", "test"],
                "noop": ["/bin/true"],
            },
            "typecheck": {
                "mypy": ["mypy", "."],
                "pyright": ["npx", "pyright"],
                "typescript": ["npx", "tsc", "--noEmit"],
                "noop": ["/bin/true"],
            },
            "format": {
                "ruff": ["ruff", "format", "."] + (["--check"] if not fix else []),
                "prettier": ["npx", "prettier", "--write", "."]
                if fix
                else ["npx", "prettier", "--check", "."],
                "rustfmt": ["cargo", "fmt"] + (["--check"] if not fix else []),
                "noop": ["/bin/true"],
            },
        }

    def run_check(self, tool_type: str, fix: bool = False, timeout: int = 300) -> dict:
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

        if self._is_noop_tool(tool):
            raise ValidationError(
                f"Tool '{tool_type}' ({tool_config_key}) is configured as the no-op "
                f"'{tool}', which skips the check. Run 'tasks config detect --save' "
                f"or set a real tool: tasks config set {tool_config_key} <tool>."
            )

        # A configured tool may be a command path (e.g. /path/to/ruff), not just a name
        if tool and tool not in commands.get(tool_type, {}):
            basename = os.path.basename(str(tool))
            if basename in commands.get(tool_type, {}):
                tool = basename

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
            result = subprocess.run(  # noqa: PLW1510
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

    def run_all(self, fix: bool = False, force: bool = False) -> list[dict]:
        """Run all configured checks."""
        results = []
        for tool in ["lint", "test", "typecheck", "format"]:
            # The pinned pytest list includes the slow pipeline suites
            # (test_robustness, test_store_writes); they run in ~8 min, so the
            # 300s default makes `check all` time out before it can report.
            results.append(self.run_check(tool, fix, timeout=900))

        return results

    def run_debug(self) -> dict:
        """Run debug messages check."""
        script_path = (
            self.project_root / "scripts" / "staging-remove-debug-messages-check.sh"
        )
        if not script_path.exists():
            raise ValidationError(f"Debug check script not found at {script_path}")

        result = subprocess.run(  # noqa: PLW1510
            [str(script_path)], cwd=self.project_root, capture_output=True, text=True
        )
        return {
            "success": result.returncode == 0,
            "tool": "debug",
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
        }
