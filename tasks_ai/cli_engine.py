import os
import shutil
import json
from pathlib import Path

from .constants import TASKS_DIR, STATE_FOLDERS
from .context import ProjectContext
from .git_client import GitClient
from .pipeline import PipelineService
from .cli_io import log, error, finish
from .file_manager import FM

class TasksCLI:
    def __init__(self, as_json=False, command=None, quiet=False, dev=False, yes=False):
        self.as_json = as_json
        self.quiet = quiet
        self.dev = dev
        self.yes = yes
        self.output_messages = []
        
        self.context = ProjectContext(dev=dev)
        self.root = self.context.repo_root or os.getcwd()

        self.git = GitClient(self.context, logger=self)
        self.pipeline = PipelineService(self.context, self.git, logger=self)

        install_dir = Path(__file__).resolve().parent.parent
        self.repo_script = str(install_dir / "repo.py")

        self.tasks_dir = TASKS_DIR
        if not dev:
            pyproject_path = self.context.resolve_path("pyproject.toml")
            if os.path.exists(pyproject_path):
                try:
                    import toml
                    with open(pyproject_path, "r") as f:
                        pyproject_data = toml.load(f)
                        self.tasks_dir = (
                            pyproject_data.get("tool", {})
                            .get("tasks_ai", {})
                            .get("tasks_dir", self.tasks_dir)
                        )
                except Exception:
                    pass

        self.context.tasks_path = self.context.resolve_path(self.tasks_dir)
        if dev:
             self.context.tasks_path = "/tmp/.tasks"
             if not os.path.exists(self.context.tasks_path):
                os.makedirs(self.context.tasks_path, exist_ok=True)
        elif os.path.isabs(self.tasks_dir):
            self.context.tasks_path = self.tasks_dir

        self.tasks_path = self.context.tasks_path
        
        if not self.tasks_path:
            self.tasks_path = os.path.join(self.root, ".tasks")
            self.context.tasks_path = self.tasks_path

        self.logs_path = os.path.join(self.tasks_path, "logs")

    def log(self, message):
        log(self, message)

    def error(self, message, hint=None):
        error(self, message, hint=hint)

    def finish(self, data=None):
        finish(self, data=data)

    def _atomic_write(self, path, task):
        FM.dump(task, path)

    def _run_git(self, cmd, cwd=None):
        return self.git.run(cmd, cwd=cwd)

    def _get_default_branch(self):
        return self.git.get_default_branch()

    def _get_next_id(self):
        from .counter import TaskCounterProtector
        protector = TaskCounterProtector(self.tasks_path, self)
        return protector.get_next_id(self)

    def _recover_task_counter_from_tasks(self):
        try:
            max_id = 0
            for state, folder in STATE_FOLDERS.items():
                state_path = os.path.join(self.tasks_path, folder)
                if not os.path.exists(state_path):
                    continue
                for item in os.listdir(state_path):
                    if item in [".gitkeep", ".task_counter", "task_counter", ".task_counter.counter_hash", ".task_counter.counter_backup", ".task_counter.counter_backup.hash"]:
                        continue
                    item_path = os.path.join(state_path, item)
                    if not os.path.isdir(item_path):
                        continue
                    if "-" in item:
                        parts = item.split("-", 1)
                        if parts[0].isdigit():
                            task_id = int(parts[0])
                            if task_id > max_id:
                                max_id = task_id
            return max_id
        except Exception:
            return 0

    def _tasks_directory_has_data(self, path):
        return os.path.exists(path) and len(os.listdir(path)) > 0

    def init(self, force=False):
        if os.path.exists(self.tasks_path):
            if self._tasks_directory_has_data(self.tasks_path):
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                backup_path = f"/tmp/.tasks.bak_{timestamp}"
                os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                self.log(f"Backing up existing .tasks to {backup_path}...")
                shutil.copytree(self.tasks_path, backup_path)
            
            if not force:
                self.error("Tasks directory already exists. Use --force to reinitialize.")
            
            shutil.rmtree(self.tasks_path)
        
        os.makedirs(self.tasks_path, exist_ok=True)
        for folder in STATE_FOLDERS.values():
            os.makedirs(os.path.join(self.tasks_path, folder), exist_ok=True)
            with open(os.path.join(self.tasks_path, folder, ".gitkeep"), "w") as f:
                f.write("")
        
        with open(os.path.join(self.tasks_path, ".task_counter"), "w") as f:
            f.write("0")
        
        self.log(f"Tasks initialized at {self.tasks_path}")

    def reconcile(self, target=None, all=False):
        if not target and not all:
            self.cleanup(dry_run=True)
        elif all:
            self.cleanup(yes=True)
        else:
            filepath, _ = self.find_task(target)
            if filepath:
                self._move_logic(target, "ARCHIVED", force=True)

    def cleanup(self, dry_run=False, yes=False):
        from .commands import cleanup as cleanup_cmd
        cleanup_cmd.run(self, dry_run=dry_run, yes=yes)

    def _move_logic(self, filename, new_status, force=False, yes=False, sync=True):
        from .commands import move as move_cmd
        move_cmd.run(self, filename, new_status, yes=yes)

    def find_task(self, filename):
        for _, folder in STATE_FOLDERS.items():
            path = os.path.join(self.tasks_path, folder, filename)
            if os.path.exists(path):
                return path, FM.load(path)
        return None, None

    def show(self, filename, section=None):
        from .commands import show as show_cmd
        show_cmd.run(self, filename, section=section)

    def _append_log(self, task_path, entry):
        if not task_path:
            return
        task_path_str = cast(str, task_path)
        log_file = os.path.join(task_path_str, "activity.log")
        timestamp = datetime.now().strftime("%y%m%d %H:%M")
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"- {timestamp}: {entry}\n")
        self._run_git(
            [
                "add",
                os.path.join(
                    os.path.relpath(task_path_str, self.tasks_path), "activity.log"
                ),
            ],
            cwd=self.tasks_path,
        )

    def _detect_tools(self):
        """Detect project type and suggest/create config."""
        detected = {}

        if os.path.exists("package.json"):
            detected["package_manager"] = "npm"
            if os.path.exists("yarn.lock"):
                detected["package_manager"] = "yarn"
            elif os.path.exists("pnpm-lock.yaml"):
                detected["package_manager"] = "pnpm"

        if os.path.exists("pyproject.toml"):
            detected["package_manager"] = "pip"
        elif os.path.exists("requirements.txt"):
            detected["package_manager"] = "pip"
        elif os.path.exists("Pipfile"):
            detected["package_manager"] = "pipenv"

        if os.path.exists("go.mod"):
            detected["language"] = "go"

        if os.path.exists("Cargo.toml"):
            detected["language"] = "rust"

        if os.path.exists("composer.json"):
            detected["language"] = "php"

        if os.path.exists("Gemfile"):
            detected["language"] = "ruby"

        lint_files = {
            "ruff.toml": "ruff",
            "pyproject.toml": "ruff",
            ".eslintrc.js": "eslint",
            ".eslintrc.json": "eslint",
            "eslint.config.js": "eslint",
            "tsconfig.json": "typescript",
            "rust-toolchain.toml": "rust",
            ".golangci.yml": "golangci-lint",
            "pylintrc": "pylint",
            ".pylintrc": "pylint",
        }

        for file, tool in lint_files.items():
            if os.path.exists(file):
                detected["lint"] = tool
                break

        type_check_files = {
            "mypy.ini": "mypy",
            "pyrightconfig.json": "pyright",
            "tsconfig.json": "typescript",
        }

        for file, tool in type_check_files.items():
            if os.path.exists(file):
                detected["type_check"] = tool
                break

        if os.path.exists("pytest.ini") or os.path.exists("pyproject.toml"):
            detected["test"] = "pytest"
        elif os.path.exists("go.mod"):
            detected["test"] = "go test"
        elif os.path.exists("Cargo.toml"):
            detected["test"] = "cargo test"

        format_files = {
            "ruff.toml": "ruff",
            "pyproject.toml": "ruff",
            ".prettierrc": "prettier",
            "rustfmt.toml": "rustfmt",
        }

        for file, tool in format_files.items():
            if os.path.exists(file):
                detected["format"] = tool
                break

        if not self.as_json:
            print("Detected tools:")
            for k, v in detected.items():
                print(f"  {k}: {v}")

            if detected:
                print("\nWould you like to save this configuration?")
                print(
                    "Run: tasks config set repo.lint " + detected.get("lint", "<tool>")
                )
                print(
                    "      tasks config set repo.type_check "
                    + detected.get("type_check", "<tool>")
                )
                print(
                    "      tasks config set repo.test " + detected.get("test", "<tool>")
                )
                print(
                    "      tasks config set repo.format "
                    + detected.get("format", "<tool>")
                )

        return detected

    def _git_merge_transition(self, task, target_state, yes=False):
        try:
            self.pipeline.git_merge_transition(task, target_state, yes=yes)
        except RuntimeError as e:
            self.error(str(e))

    def _generate_review_diff(self, task_path, branch):
        """Generate a unified diff patch for the task branch against main including unstaged changes."""
        review_dir = os.path.join(self.tasks_path, STATE_FOLDERS["REVIEW"])
        task_id = os.path.basename(task_path)
        diff_path = os.path.join(review_dir, f"{task_id}.patch")

        os.makedirs(review_dir, exist_ok=True)
        # early debug
        debug_log = f"/tmp/review_diff_debug_{os.getuid()}.log"
        try:
            with open(debug_log, "a") as f:
                f.write(f"ENTER: task_id={task_id}, branch={branch}\\n")
        except (PermissionError, OSError):
            pass
        self.log(
            f"[DEBUG] Generating review diff: task_id={task_id}, branch={branch}"
        )

        # Get commits diff: default_branch...HEAD (commits on branch not in default branch)
        # Use merge-base to find common ancestor
        default_branch = self._get_default_branch()
        main_sha = None
        try:
            main_sha = self._run_git(["rev-parse", default_branch]).stdout.strip()
        except Exception:
            main_sha = None

        self.log(
            f"[DEBUG] branch={branch}, default_branch={default_branch}, main_sha={main_sha}"
        )
        debug_log2 = f"/tmp/review_diff_debug_{os.getuid()}.log"
        try:
            with open(debug_log2, "a") as f:
                f.write(f"branch={branch}, default_branch={default_branch}, main_sha={main_sha}\\n")
        except (PermissionError, OSError):
            pass

        diff_content = ""

        if main_sha:
            # Get diff between fork point and branch: git diff <main_sha>...<branch>
            # Three dots means: diff between the common ancestor of main and branch, and branch.
            result = self._run_git(
                ["diff", f"{default_branch}...{branch}"], cwd=self.root
            )
            self.log(
                f"[DEBUG] branch-diff cmd returncode={result.returncode}, stdout len={len(result.stdout)}"
            )
            if result.returncode == 0 and result.stdout.strip():
                diff_content += result.stdout
            else:
                self.log(f"[DEBUG] branch-diff cmd stderr: {result.stderr}")

        # Get unstaged working tree changes
        result = self._run_git(["diff", "--patch"], cwd=self.root)
        self.log(
            f"[DEBUG] unstaged diff returncode={result.returncode}, stdout len={len(result.stdout)}"
        )
        if result.returncode == 0 and result.stdout:
            if diff_content and not diff_content.endswith("\\n"):
                diff_content += "\\n"
            diff_content += result.stdout

        # Get staged changes
        result = self._run_git(["diff", "--cached", "--patch"], cwd=self.root)
        if result.returncode == 0 and result.stdout:
            if diff_content and not diff_content.endswith("\\n"):
                diff_content += "\\n"
            diff_content += f"# Staged changes:\\n{result.stdout}"

        # Write diff file
        with open(diff_path, "w", encoding="utf-8") as f:
            f.write(diff_content or "# No changes detected\\n")

        # Debug: record values to a file in repo root
        debug_path = os.path.join(self.root, "diff_debug.log")
        with open(debug_path, "a") as f:
            f.write(
                f"branch={branch}, main_sha={main_sha}, diff_len={len(diff_content)}\\n"
            )

        self.log(f"Regression diff generated at {diff_path}")
        return diff_path

    def list(self, show_all=False):
    def _push_tasks_branch(self, branch="tasks", fatal=True):
        """Internal: push current .tasks worktree branch to remote.
        If fatal=False, returns result dict or None on failure; does not exit.
        If fatal=True, calls self.error() on failure (exits)."""
        if not os.path.exists(self.tasks_path):
            msg = "Tasks not initialized. Run 'hammer tasks init' first."
            if fatal:
                self.error(msg)
            return None
        remotes = self._run_git(["remote", "-v"], cwd=self.tasks_path)
        if not remotes.stdout.strip():
            if self.dev or self.yes:
                current = self._run_git(
                    ["rev-parse", "--abbrev-ref", "HEAD"], cwd=self.tasks_path
                ).stdout.strip()
                self.log(
                    "No remote configured - skipping push (local-only mode)"
                )
                return {"branch": branch, "remote": None, "from_branch": current}
            else:
                msg = "No remote configured in .tasks. Set up a remote or use --dev / -y flag."
                if fatal:
                    self.error(msg)
                return None
        current = self._run_git(
            ["rev-parse", "--abbrev-ref", "HEAD"], cwd=self.tasks_path
        ).stdout.strip()
        push_result = self._run_git(
            ["push", "-u", "origin", f"{current}:refs/heads/{branch}"],
            cwd=self.tasks_path,
        )
        if push_result.returncode != 0:
            msg = f"Failed to push .tasks worktree to remote: {push_result.stderr}"
            if fatal:
                self.error(msg)
            else:
                self.log(f"Warning: {msg}")
                return None
        self.log(f"Pushed .tasks ({current}) to origin/{branch}")
        return {"branch": branch, "remote": "origin", "from_branch": current}
    def get_active_task(self, filename=None):
        if filename:
            filepath, _ = self.find_task(filename)
            if filepath:
                return filepath, FM.load(filepath)
            return None, None
        prog_dir = os.path.join(self.tasks_path, STATE_FOLDERS["PROGRESSING"])
        if os.path.exists(prog_dir):
            dirs = [
                d
                for d in os.listdir(prog_dir)
                if os.path.isdir(os.path.join(prog_dir, d)) and d != ".gitkeep"
            ]
            if dirs:
                filepath = os.path.join(prog_dir, dirs[0])
                return filepath, FM.load(filepath)
        return None, None
    def _validate_pipeline_gate(self, task, target_state):
        task_id = str(task.metadata.get("Id"))
        filepath, _ = self.find_task(task_id)
        if not filepath:
            return

        try:
            self.pipeline.validate_gate(task, target_state, filepath)
        except PipelineError as e:
            self.error(str(e), hint=e.hint)
    def _validate_path(self, path):
        """Ensure path is within tasks_path to prevent traversal."""
        if not path:
            return False
        abs_tasks = os.path.abspath(self.tasks_path)
        abs_target = os.path.abspath(path)
        return abs_target.startswith(abs_tasks)
    def _run_validation(self, fix=False):
        check_path = os.path.join(self.root, "check.py")
        if not os.path.exists(check_path):
            return
        result = subprocess.run(
            [sys.executable, check_path, "lint"] + (["--fix"] if fix else []),
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            self.error(
                "Validation failed. Fix errors before proceeding.",
                hint="Run 'hammer check lint' to see errors. Do not bypass this tool.",
            )
    def _run_tests(self, fail_safe=False):
        check_path = os.path.join(self.root, "check.py")
        if not os.path.exists(check_path):
            return subprocess.CompletedProcess("", 0)
        result = subprocess.run(
            [sys.executable, check_path, "test"],
            cwd=self.root,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            if fail_safe:
                return result
            self.error(
                "Tests failed. Fix test failures before proceeding.",
                hint="Run 'hammer check test' to see failures. Do not bypass this tool.",
            )
        return result
        from .commands import list as list_cmd
        list_cmd.run(self, show_all=show_all)
