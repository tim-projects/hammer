# tasks_ai/cli.py
import os
import sys  # type: ignore[attr-defined]
import subprocess
import tempfile
import re
import json
import shutil
import fcntl
import hashlib
from typing import cast
from datetime import datetime, timedelta
from pathlib import Path

from .constants import (
    TASKS_DIR,
    TASKS_BRANCH,
    CURRENT_TASK_FILENAME,
    STATE_FOLDERS,
    ALLOWED_TRANSITIONS,
    ALLOWED_CONFIG_KEYS,
)
from .file_manager import FM
from .context import ProjectContext
from .git_client import GitClient
from .pipeline import PipelineService, PipelineError


def get_terminal_width():
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80


class TasksCLI:
    def __init__(self, as_json=False, command=None, quiet=False, dev=False, yes=False):
        self.as_json = as_json
        self.quiet = quiet
        self.dev = dev
        self.yes = yes
        self.output_messages = []
        
        # Phase 1: Context & Path Abstraction
        self.context = ProjectContext(dev=dev)
        self.root = self.context.repo_root

        # Phase 2: Logic Extraction (Modularization)
        self.git = GitClient(self.context, logger=self)
        self.pipeline = PipelineService(self.context, self.git, logger=self)

        # Resolve absolute path to repo.py (works for both source checkout and system install)
        install_dir = Path(__file__).resolve().parent.parent
        self.repo_script = str(install_dir / "repo.py")

        # Determine tasks directory
        self.tasks_dir = TASKS_DIR
        if not dev:
            # Check pyproject.toml for override first (project-wide)
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
                except ImportError:
                    pass
                except Exception:
                    pass

        # Update context with potentially overridden tasks_dir
        self.context.tasks_path = self.context.resolve_path(self.tasks_dir)
        if dev:
             self.context.tasks_path = "/tmp/.tasks"
             if not os.path.exists(self.context.tasks_path):
                os.makedirs(self.context.tasks_path, exist_ok=True)
        elif os.path.isabs(self.tasks_dir):
            self.context.tasks_path = self.tasks_dir

        self.tasks_path = self.context.tasks_path

        # Now that self.tasks_path is set, we can check .tasks/config.yaml if not in dev mode
        if not dev:
            cfg = self._get_config()
            if cfg and isinstance(cfg, dict) and "tasks_dir" in cfg:
                td = cfg["tasks_dir"]
                if td:
                    self.tasks_dir = str(td)
                    if os.path.isabs(self.tasks_dir):
                        self.tasks_path = self.tasks_dir
                    else:
                        self.tasks_path = self.context.resolve_path(self.tasks_dir)
                    self.context.tasks_path = self.tasks_path

        self.logs_path = os.path.join(self.tasks_path, "logs")
        if os.path.exists(self.tasks_path):
            self._migrate_live_to_done()
            self._auto_archive()
            if command and command != "delete":
                self._clear_delete_marks()

    def _migrate_live_to_done(self):
        """Migrate .tasks/live to .tasks/done if it exists."""
        live_dir = os.path.join(self.tasks_path, "live")
        done_dir = os.path.join(self.tasks_path, "done")

        if os.path.exists(live_dir):
            # Check if there are actual tasks (not just .gitkeep)
            items = [i for i in os.listdir(live_dir) if i != ".gitkeep"]
            if items:
                self.log(f"Migrating {len(items)} tasks from LIVE to DONE...")
                os.makedirs(done_dir, exist_ok=True)
                for item in items:
                    src = os.path.join(live_dir, item)
                    dst = os.path.join(done_dir, item)
                    if os.path.exists(os.path.join(self.tasks_path, ".git")):
                        # Use git mv if it's a git repo and tracked
                        res = self._run_git(
                            [
                                "mv",
                                os.path.join("live", item),
                                os.path.join("done", item),
                            ],
                            cwd=self.tasks_path,
                        )
                        if res.returncode != 0:
                            if os.path.exists(dst):
                                if os.path.isdir(dst):
                                    shutil.rmtree(dst)
                                else:
                                    os.remove(dst)
                            shutil.move(src, dst)
                    else:
                        if os.path.exists(dst):
                            if os.path.isdir(dst):
                                shutil.rmtree(dst)
                            else:
                                os.remove(dst)
                        shutil.move(src, dst)

                # Commit migration if in git
                if os.path.exists(os.path.join(self.tasks_path, ".git")):
                    self._run_git(["add", "--all"], cwd=self.tasks_path)
                    self._run_git(
                        ["commit", "-m", "Migrate LIVE tasks to DONE"],
                        cwd=self.tasks_path,
                    )
                self.log("Migration complete.")

            # Remove live directory if empty or only contains .gitkeep
            remaining = os.listdir(live_dir)
            if not remaining or (len(remaining) == 1 and remaining[0] == ".gitkeep"):
                try:
                    if os.path.exists(os.path.join(self.tasks_path, ".git")):
                        self._run_git(["rm", "-rf", "live"], cwd=self.tasks_path)
                    if os.path.exists(live_dir):
                        shutil.rmtree(live_dir)
                except Exception:
                    pass

    def _clear_delete_marks(self):
        updated = False
        for state, folder in STATE_FOLDERS.items():
            dir_path = os.path.join(self.tasks_path, folder)
            if not os.path.exists(dir_path):
                continue
            for item in os.listdir(dir_path):
                if item == ".gitkeep":
                    continue
                path = os.path.join(dir_path, item)
                try:
                    task = FM.load(path)
                    if task and task.metadata and "DeleteCode" in task.metadata:
                        del task.metadata["DeleteCode"]
                        self._atomic_write(path, task)
                        updated = True
                except Exception as e:
                    self.log(f"Warning: Failed to load task at {path}: {e}")
        if updated:
            self._run_git(["add", "--all"], cwd=self.tasks_path)
            self._run_git(
                ["commit", "--allow-empty", "-m", "Clear delete marks"],
                cwd=self.tasks_path,
            )

    def _validate_task_id(self, task_id):
        """Validate task ID format (numeric or slug)."""
        if task_id is None:
            return False
        task_id_str = str(task_id)
        if not task_id_str:
            return False
        # Allow numeric IDs or task slugs (e.g., "1-task-title")
        return bool(re.match(r"^[a-zA-Z0-9\-_.]+$", task_id_str))

    def _validate_path(self, path):
        """Ensure path is within tasks_path to prevent traversal."""
        if not path:
            return False
        abs_tasks = os.path.abspath(self.tasks_path)
        abs_target = os.path.abspath(path)
        return abs_target.startswith(abs_tasks)

    def _get_git_root(self):
        try:
            return (
                subprocess.check_output(
                    ["git", "rev-parse", "--show-toplevel"], stderr=subprocess.DEVNULL
                )
                .decode()
                .strip()
            )
        except subprocess.CalledProcessError:
            self.error("Not a git repository. Run 'git init' to start.")
            sys.exit(1)

    def _git_merge_transition(self, task, target_state, yes=False):
        try:
            self.pipeline.git_merge_transition(task, target_state, yes=yes)
        except RuntimeError as e:
            self.error(str(e))

    def _validate_pipeline_gate(self, task, target_state):
        task_id = str(task.metadata.get("Id"))
        filepath, _ = self.find_task(task_id)
        if not filepath:
            return

        try:
            self.pipeline.validate_gate(task, target_state, filepath)
        except PipelineError as e:
            self.error(str(e), hint=e.hint)

    def _run_git(self, args, cwd=None):
        result = self.git.run(args, cwd=cwd)

        # If in dev mode and command fails in tasks_path, it might not be a git repo
        if result.returncode != 0 and self.dev and (cwd == self.tasks_path or cwd is None and self.git.context.repo_root == self.tasks_path):
            return result

        return result

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
                f.write(f"ENTER: task_id={task_id}, branch={branch}\n")
        except (PermissionError, OSError):
            pass
        self.log(
            f"[DEBUG] Generating review diff: task_id={task_id}, branch='{branch}'"
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
                f.write(f"branch={branch}, default_branch={default_branch}, main_sha={main_sha}\n")
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
            if diff_content and not diff_content.endswith("\n"):
                diff_content += "\n"
            diff_content += result.stdout

        # Get staged changes
        result = self._run_git(["diff", "--cached", "--patch"], cwd=self.root)
        if result.returncode == 0 and result.stdout:
            if diff_content and not diff_content.endswith("\n"):
                diff_content += "\n"
            diff_content += f"# Staged changes:\n{result.stdout}"

        # Write diff file
        with open(diff_path, "w", encoding="utf-8") as f:
            f.write(diff_content or "# No changes detected\n")

        # Debug: record values to a file in repo root
        debug_path = os.path.join(self.root, "diff_debug.log")
        with open(debug_path, "a") as f:
            f.write(
                f"branch={branch}, main_sha={main_sha}, diff_len={len(diff_content)}\n"
            )

        self.log(f"Regression diff generated at {diff_path}")
        return diff_path

    def _check_transition(self, filename, new_status):
        filepath, current_state = self.find_task(filename)
        if not filepath or current_state is None:
            return
        if "," in new_status:
            return
        if (
            new_status not in ALLOWED_TRANSITIONS.get(current_state, [])
            and current_state != new_status
        ):
            if current_state == "BACKLOG" and new_status == "PROGRESSING":
                self.log("Auto-promoting BACKLOG to READY before PROGRESSING.")
                self.log("REMINDER: Ensure the task is fully populated with 'story', 'tech', 'criteria', and 'plan' fields to meet the READY gate.")
                self._move_logic(filename, "READY", yes=True)
                return
            self.error(f"Forbidden transition: {current_state} -> {new_status}")

    def _run_repo(self, args, cwd=None):
        cwd = cwd or self.root
        repo_path = os.path.join(self.root, "repo")
        result = subprocess.run(
            [repo_path] + args, cwd=cwd, capture_output=True, text=True
        )
        return result

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

    def _parse_filename(self, name):
        if not name:
            return "task", ""
        name_part = str(name).rsplit(".", 1)[0]
        if "-" in name_part:
            parts = name_part.split("-", 2)
            if len(parts) >= 3:
                return parts[1], name_part
        if "_" in name_part:
            return name_part.split("_", 1)
        return "task", name_part

    def _atomic_write(self, path, task_or_content):
        """Write a task or content to a path atomically."""
        if path is None:
            self.error("DEBUG: _atomic_write path is None!")
            return

        if hasattr(task_or_content, "metadata"):
            # It's a Task object, use FM.dump
            if path.endswith(".md"):
                FM.dump(task_or_content, path)
            else:
                # Directory-based task
                parent_dir = os.path.dirname(path.rstrip("/"))
                os.makedirs(parent_dir, exist_ok=True)
                temp_dir = tempfile.mkdtemp(dir=parent_dir)
                try:
                    FM.dump(task_or_content, temp_dir)
                    if os.path.exists(path):
                        if os.path.isdir(path):
                            shutil.rmtree(path)
                        else:
                            os.remove(path)
                    os.rename(temp_dir, path)
                except Exception as e:
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)
                    raise e
        else:
            # It's raw content (string or bytes)
            content = task_or_content
            if not isinstance(content, str):
                try:
                    content = content.decode("utf-8")
                except (AttributeError, UnicodeDecodeError):
                    content = str(content)
            
            dir_name = os.path.dirname(path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            
            fd, temp_path = tempfile.mkstemp(dir=dir_name or ".", text=True)
            try:
                with os.fdopen(fd, "w") as f:
                    f.write(content)
                os.replace(temp_path, path)
            except Exception as e:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                raise e

    def log(self, message):
        if self.as_json:
            self.output_messages.append(message)
        elif not self.quiet:
            print(message)

    def error(self, message, hint=None):
        if self.quiet:
            pass
        elif self.as_json:
            response = {
                "success": False,
                "error": message,
                "messages": self.output_messages,
            }
            if hint:
                response["hint"] = hint
            print(json.dumps(response))
            sys.exit(1)
        else:
            if hint:
                message = f"{message} | HINT: {hint}"
            print(f"Error: {message}", file=sys.stderr)
            sys.exit(1)

    def finish(self, data=None):
        if self.quiet:
            pass
        elif self.as_json:
            print(
                json.dumps(
                    {"success": True, "messages": self.output_messages, "data": data},
                    indent=2,
                )
            )
        if not hasattr(sys, "_called_from_test"):
            sys.exit(0)

    def _auto_archive(self):
        for state in ["DONE"]:
            folder = STATE_FOLDERS.get(state)
            if not folder:
                continue
            target_dir = os.path.join(self.tasks_path, folder)
            if not os.path.exists(target_dir):
                continue
            now = datetime.now()
            for item in os.listdir(target_dir):
                if item == ".gitkeep":
                    continue
                path = os.path.join(target_dir, item)
                if os.path.isdir(path):
                    log_path = os.path.join(path, "activity.log")
                    if os.path.exists(log_path):
                        with open(log_path, "r", encoding="utf-8") as f:
                            lines = f.readlines()
                        done_date = None
                        for line in reversed(lines):
                            if "->DONE" in line:
                                match = re.search(r"- (\d{6} \d{2}:\d{2}):", line)
                                if match:
                                    done_date = datetime.strptime(
                                        match.group(1), "%y%m%d %H:%M"
                                    )
                                    break
                        if done_date and (now - done_date) > timedelta(days=7):
                            if self.pipeline.has_incomplete_checkboxes(path):
                                self.log(
                                    f"Skipping archive for {item}: incomplete checkboxes"
                                )
                                continue
                            self.log(f"Auto-archiving: {item}")
                            self._move_logic(item, "ARCHIVED", force=True, yes=False)

    def _tasks_directory_has_data(self, path):
        """Check if .tasks directory contains actual task data beyond infrastructure."""
        if not os.path.exists(path):
            return False
        # .task_counter presence indicates tasks have been created
        if os.path.exists(os.path.join(path, ".task_counter")):
            return True
        # Check each state folder for task directories (anything beyond .gitkeep)
        for state_folder in STATE_FOLDERS.values():
            folder_path = os.path.join(path, state_folder)
            if not os.path.isdir(folder_path):
                continue
            for item in os.listdir(folder_path):
                if item == ".gitkeep":
                    continue
                # Anything else in a state folder is a task directory or file
                return True
        # Check for logs directory with any content
        logs_path = os.path.join(path, "logs")
        if os.path.isdir(logs_path) and os.listdir(logs_path):
            return True
        return False

    def init(self, force=False):
        def install_hooks(self):
            hook_dir = os.path.join(self.root, ".git", "hooks")
            hook_path = os.path.join(hook_dir, "pre-merge")
            
            # Ensure hook directory exists
            if not os.path.exists(hook_dir):
                return

            # Explicitly overwrite ONLY the pre-merge hook
            with open(hook_path, "w") as f:
                f.write("#!/bin/bash\n\nif [ \"$HAMMER_INTERNAL_MERGE\" == \"1\" ]; then\n    exit 0\nfi\ntarget_branch=$(git rev-parse --abbrev-ref HEAD)\nif [ \"$target_branch\" == \"main\" ]; then\n    echo \"⚠️  Direct git merge to main detected. Pipeline governance requires './hammer repo merge'. Aborting.\"\n    exit 1\nfi")
            os.chmod(hook_path, 0o755)

            # Install post-merge hook for pipeline sync monitoring
            post_merge_path = os.path.join(hook_dir, "post-merge")
            with open(post_merge_path, "w") as f:
                f.write("#!/bin/bash\n\nif [ \"$HAMMER_INTERNAL_MERGE\" == \"1\" ]; then\n    exit 0\nfi\n\ntarget_branch=$(git rev-parse --abbrev-ref HEAD)\nif [ \"$target_branch\" == \"main\" ]; then\n    echo \"Checking pipeline sync...\"\n    staging_diff=$(git log main..staging --oneline)\n    testing_diff=$(git log staging..testing --oneline)\n    if [ -n \"$staging_diff\" ] || [ -n \"$testing_diff\" ]; then\n        echo \"⚠️  Pipeline branches (staging/testing) are out of sync with main!\"\n        echo \"Run './hammer repo sync' to reconcile.\"\n    else\n        echo \"✅ Pipeline branches are in sync.\"\n    fi\nfi")
            os.chmod(post_merge_path, 0o755)

            # Install pre-receive hook to prevent deletion of critical branches
            pre_receive_path = os.path.join(hook_dir, "pre-receive")
            with open(pre_receive_path, "w") as f:
                f.write("#!/bin/bash\n\nwhile read oldrev newrev refname; do\n    if [[ \"$newrev\" == \"0000000000000000000000000000000000000000\" ]]; then\n        branch=$(basename \"$refname\")\n        if [[ \"$branch\" == \"main\" || \"$branch\" == \"staging\" || \"$branch\" == \"testing\" ]]; then\n            echo \"❌ Cannot delete critical pipeline branch: $branch\"\n            exit 1\n        fi\n    fi\ndone")
            os.chmod(pre_receive_path, 0o755)

            # Prevent local deletion via pre-commit (simulated)
            pre_commit_path = os.path.join(hook_dir, "pre-commit")
            with open(pre_commit_path, "w") as f:
                f.write("#!/bin/bash\n\n# Prevent accidental branch deletion in git branch -d commands\n# Note: This is a best-effort local protection.\nif git rev-parse --verify HEAD >/dev/null 2>&1; then\n   # Logic to check for branch delete commands not easily done in pre-commit\n   : \nfi")
            os.chmod(pre_commit_path, 0o755)

        
        if self.dev:
            # Ensure the base directory exists first
            if not os.path.exists(self.tasks_path):
                os.makedirs(self.tasks_path, exist_ok=True)
                
            for folder in list(STATE_FOLDERS.values()):
                p = os.path.join(self.tasks_path, folder)
                if not os.path.exists(p):
                    os.makedirs(p, exist_ok=True)
                    Path(os.path.join(p, ".gitkeep")).touch()

            counter_file = os.path.join(self.tasks_path, ".task_counter")
            if not os.path.exists(counter_file):
                with open(counter_file, "w") as f:
                    f.write("0")

            git_dir = os.path.join(self.tasks_path, ".git")
            if not os.path.exists(git_dir):
                subprocess.run(
                    ["git", "init"], cwd=self.tasks_path, capture_output=True
                )
                subprocess.run(
                    ["git", "add", "."], cwd=self.tasks_path, capture_output=True
                )
                subprocess.run(
                    [
                        "git",
                        "commit",
                        "--allow-empty",
                        "-m",
                        "Initial dev tasks commit",
                    ],
                    cwd=self.tasks_path,
                    capture_output=True,
                )

            self.log(f"Dev tasks initialized at {self.tasks_path}")
            self.finish()
            return

        original_branch = self._run_git(["branch", "--show-current"]).stdout.strip()
        branches = self._run_git(["branch"]).stdout
        if TASKS_BRANCH not in branches:
            self._run_git(["checkout", "--orphan", TASKS_BRANCH])
            self._run_git(["reset", "--hard"])
            self._run_git(["commit", "--allow-empty", "-m", "Initial tasks commit"])
            if original_branch:
                self._run_git(["checkout", original_branch])
            else:
                self._run_git(["checkout", "-"])
        # Ensure .tasks is in .gitignore
        gitignore_path = os.path.join(self.root, ".gitignore")
        ignore_line = f"/{TASKS_DIR}/"
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r") as f:
                content = f.read()
            if ignore_line not in content:
                with open(gitignore_path, "a") as f:
                    f.write(f"\n{ignore_line}\n")
        else:
            with open(gitignore_path, "w") as f:
                f.write(f"{ignore_line}\n")

        # Ensure .tasks is not already tracked
        self._run_git(["rm", "-rf", "--cached", TASKS_DIR], cwd=self.root)

        is_worktree = False
        if os.path.exists(self.tasks_path):
            wt_res = self._run_git(["worktree", "list", "--porcelain"])
            if self.tasks_path in wt_res.stdout:
                is_worktree = True

        if not is_worktree:
            # Clean up non-worktree .tasks if exists
            if os.path.exists(self.tasks_path):
                # Safety check: create a backup
                if self._tasks_directory_has_data(self.tasks_path):
                    from datetime import datetime
                    repo_name = os.path.basename(self.root.rstrip('/'))
                    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                    backup_path = f"/tmp/.tasks.bak_{timestamp}"
                    os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                    self.log(f"Backing up existing .tasks to {backup_path}...")
                    shutil.copytree(self.tasks_path, backup_path)
                    
                    if not force:
                        self.error(
                            f"Found existing .tasks directory with data at '{self.tasks_path}'. "
                            "Running 'hammer init' here would permanently delete all task history.\n"
                            "Hint: Run 'hammer tasks doctor' to diagnose and repair issues. "
                            "Use 'hammer init --force' only if you are certain you want to reset."
                        )
                if os.path.isdir(self.tasks_path):
                    shutil.rmtree(self.tasks_path)
                else:
                    os.remove(self.tasks_path)
            
            # Re-create as worktree
            self._run_git(["worktree", "add", self.tasks_path, TASKS_BRANCH], cwd=self.root)
        for folder in list(STATE_FOLDERS.values()):
            p = os.path.join(self.tasks_path, folder)
            if not os.path.exists(p):
                os.makedirs(p)
                Path(os.path.join(p, ".gitkeep")).touch()
                self._run_git(
                    ["add", os.path.join(folder, ".gitkeep")], cwd=self.tasks_path
                )
        st = self._run_git(["status", "--porcelain"], cwd=self.tasks_path)
        if st.stdout:
            self._run_git(
                ["commit", "--allow-empty", "-m", "Init tasks folders"],
                cwd=self.tasks_path,
            )

        counter_file = os.path.join(self.tasks_path, ".task_counter")
        if not os.path.exists(counter_file):
            with open(counter_file, "w") as f:
                f.write("0")
            self._run_git(["add", ".task_counter"], cwd=self.tasks_path)
            self._run_git(
                ["commit", "--allow-empty", "-m", "Init task counter"],
                cwd=self.tasks_path,
            )

        gitignore_path = os.path.join(self.root, ".gitignore")
        ignore_line = f"{TASKS_DIR}/"
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r") as f:
                content = f.read()
            if ignore_line not in content:
                with open(gitignore_path, "a") as f:
                    f.write(f"\n{ignore_line}\n")
        else:
            with open(gitignore_path, "w") as f:
                f.write(f"{ignore_line}\n")
        self.log("Tasks initialized.")
        # Configure auto-merge settings
        subprocess.run(["git", "config", "--global", "merge.message", "merge: auto-merge"], cwd=self.root)
        os.environ["GIT_MERGE_AUTOEDIT"] = "no"
        self.log("Git auto-merge configured.")
        self.log(
            'Tip: Create a task with: tasks create "Your task title" --story "As a user..." --tech "..." --criteria "..." --plan "1. ..."'
        )
        self.log("Use -j for JSON output. Run 'list' to see all tasks with their Ids.")
        self.finish()


    def save(self, branch="tasks"):
        from .commands import save as save_cmd
        result = save_cmd.run(self, branch=branch, fatal=True)
        self.finish(result)

    def restore(self, branch="tasks", force=False):
        """Restore .tasks worktree from the specified backup branch."""
        tasks_path = self.tasks_path
        if os.path.exists(tasks_path):
            if force:
                self.log(
                    f"WARNING: {tasks_path} exists. --force specified, will overwrite."
                )
                # Remove existing .tasks
                if os.path.isdir(tasks_path):
                    shutil.rmtree(tasks_path)
                else:
                    os.remove(tasks_path)
            else:
                self.error(
                    f"The directory '{tasks_path}' already exists. Use --force to overwrite, or delete it first.",
                    hint="If you need to recover a deleted .tasks, ensure it is completely removed before running restore.",
                )
        # Ensure we are in the main git repository
        # Fetch latest from remote to get backup branch
        fetch_res = self._run_git(["fetch", "origin"], cwd=self.root)
        if fetch_res.returncode != 0:
            self.error(f"Failed to fetch from remote: {fetch_res.stderr}")
        # Prune any stale worktree references
        self._run_git(["worktree", "prune"], cwd=self.root, check=False)
        # Check if local branch exists
        branch_check = self._run_git(["branch", "--list", branch], cwd=self.root)
        if branch_check.returncode == 0 and branch in branch_check.stdout:
            # Local branch exists; use it
            self._run_git(["worktree", "add", tasks_path, branch], cwd=self.root)
        else:
            # Check remote branch
            remote_check = self._run_git(
                ["ls-remote", "--heads", "origin", branch], cwd=self.root
            )
            if not remote_check.stdout.strip():
                self.error(
                    f"Branch '{branch}' not found locally or on remote. Cannot restore."
                )
            # Create local branch from remote and add worktree
            self._run_git(
                ["worktree", "add", "-b", branch, tasks_path, f"origin/{branch}"],
                cwd=self.root,
            )
        self.log(f"Restored .tasks worktree from branch '{branch}' at {tasks_path}")
        self.finish({"restored": True, "branch": branch, "path": tasks_path})

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

    def find_task(self, name):
        """Find a task by its ID or filename."""
        if name is None:
            return None, None
        name = str(name)
        if not name or not self._validate_task_id(name):
            return None, None
        
        # If it looks like a numeric ID, prioritize finding by metadata ID
        task_id = name.rsplit(".", 1)[0]
        
        matches = []
        
        # 1. Quick check: directory named EXACTLY task_id or starts with task_id + '-'
        for state, folder in STATE_FOLDERS.items():
            state_dir = os.path.join(self.tasks_path, folder)
            if not os.path.exists(state_dir):
                continue
            
            # Direct match
            direct_path = os.path.join(state_dir, task_id)
            if os.path.isdir(direct_path):
                matches.append((direct_path, state))
            
            # Match by prefix (e.g. "123-task-name")
            if task_id.isdigit():
                prefix = f"{task_id}-"
                for item in os.listdir(state_dir):
                    if item.startswith(prefix):
                        path = os.path.join(state_dir, item)
                        if os.path.isdir(path):
                            matches.append((path, state))

        # 2. Exhaustive check (only if no matches found yet and it's a numeric ID)
        if not matches and task_id.isdigit():
            for state, folder in STATE_FOLDERS.items():
                fp = os.path.join(self.tasks_path, folder)
                if not os.path.exists(fp):
                    continue
                for item in os.listdir(fp):
                    if item == ".gitkeep":
                        continue
                    path = os.path.join(fp, item)
                    if os.path.isdir(path):
                        try:
                            task = FM.load(path)
                            if str(task.metadata.get("Id")) == task_id:
                                matches.append((path, state))
                        except Exception:
                            continue

        if not matches:
            return None, None

        # Prioritization: prefer non-ARCHIVED states if multiple matches
        selected = None
        if len(matches) == 1:
            selected = matches[0]
        else:
            # Prefer active states
            for path, state in matches:
                if state not in ("ARCHIVED", "REJECTED", "BACKLOG"):
                    selected = (path, state)
                    break
            if not selected:
                # Then prefer READY/BACKLOG
                for path, state in matches:
                    if state in ("READY", "BACKLOG"):
                        selected = (path, state)
                        break
            if not selected:
                selected = matches[0]

        if selected and self._validate_path(selected[0]):
            return selected
        return None, None


    def _calculate_file_hash(self, filepath):
        """Calculate SHA256 hash of a file"""
        try:
            hash_sha256 = hashlib.sha256()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception:
            return None

    def _write_counter_hash(self, counter_file, hash_file):
        """Write hash of counter file to hash file using atomic write"""
        try:
            file_hash = self._calculate_file_hash(counter_file)
            if file_hash:
                self._atomic_write(hash_file, file_hash)
        except Exception:
            pass  # Fail silently for hash writing

    def _verify_counter_hash(self, counter_file, hash_file):
        """Verify that counter file matches its hash"""
        if not os.path.exists(hash_file):
            return False
        try:
            with open(hash_file, "r") as f:
                stored_hash = f.read().strip()
            calculated_hash = self._calculate_file_hash(counter_file)
            return stored_hash == calculated_hash
        except Exception:
            return False

    def _recover_task_counter_from_tasks(self):
        """Recover task counter by scanning existing task IDs"""
        try:
            max_id = 0
            # Scan all state folders for existing tasks
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
                    # Try to get ID from directory name (format: {id}-{type}-{title})
                    if "-" in item:
                        parts = item.split("-", 1)
                        if parts[0].isdigit():
                            task_id = int(parts[0])
                            if task_id > max_id:
                                max_id = task_id
                    # Also check metadata.json for ID as fallback
                    meta_path = os.path.join(item_path, "meta.json")
                    if os.path.exists(meta_path):
                        try:
                            import json
                            with open(meta_path, "r") as f:
                                meta = json.load(f)
                            meta_id = meta.get("Id")
                            if meta_id and str(meta_id).isdigit():
                                task_id = int(meta_id)
                                if task_id > max_id:
                                    max_id = task_id
                        except Exception:
                            pass
            # Also check remote branches for higher IDs
            try:
                # Get remote branch names that might contain task IDs
                result = self._run_git(["ls-remote", "--heads", "origin"], cwd=self.root)
                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        if not line:
                            continue
                        parts = line.split('\t')
                        if len(parts) >= 2:
                            ref = parts[1]
                            # Look for refs like refs/heads/123-task-name
                            if ref.startswith("refs/heads/"):
                                branch_name = ref[11:]  # Remove refs/heads/
                                if "-" in branch_name:
                                    branch_parts = branch_name.split("-", 1)
                                    if branch_parts[0].isdigit():
                                        branch_id = int(branch_parts[0])
                                        if branch_id > max_id:
                                            max_id = branch_id
            except Exception:
                pass  # Fail silently for remote check
            
            return max_id if max_id > 0 else None
        except Exception:
            return None

    def _get_next_id(self):
        """Get the next task ID with protection and recovery mechanisms"""
        protector = TaskCounterProtector(self.tasks_path, self)
        return protector.get_next_id(self)

    def create(
        self,
        title,
        task_type="task",
        priority=None,
        story=None,
        tech=None,
        criteria=None,
        plan=None,
        repro=None,
        branch=False,
    ):
        from .commands import create as create_cmd
        create_cmd.run(
            self,
            title,
            task_type=task_type,
            priority=priority,
            story=story,
            tech=tech,
            criteria=criteria,
            plan=plan,
            repro=repro,
            branch=branch,
        )

    def modify(
        self,
        filename,
        task_type=None,
        title=None,
        story=None,
        tech=None,
        criteria=None,
        plan=None,
        repro=None,
        notes=None,
        progress=None,
        findings=None,
        mitigations=None,
        tests_passed=None,
        priority=None,
        regression_check=None,
    ):
        from .commands import modify as modify_cmd
        modify_cmd.run(
            self,
            filename,
            task_type=task_type,
            title=title,
            story=story,
            tech=tech,
            criteria=criteria,
            plan=plan,
            repro=repro,
            notes=notes,
            progress=progress,
            findings=findings,
            mitigations=mitigations,
            tests_passed=tests_passed,
            priority=priority,
            regression_check=regression_check,
        )

    def delete(self, filename, confirm=None):
        from .commands import delete as delete_cmd
        delete_cmd.run(self, filename, confirm=confirm)

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

    def checkpoint(self, filename=None):
        from .commands import checkpoint as cp_cmd
        cp_cmd.run(self, filename=filename)

    def _sync_task_content(self, filepath, task, is_final=False):
        if not filepath:
            return False
        filepath_str = cast(str, filepath)
        tn = os.path.basename(filepath_str)
        _, branch = self._parse_filename(tn)
        updated = False
        res = self._run_git(
            ["log", branch, f"^{self._get_default_branch()}", "--oneline"]
        )
        commits = res.stdout.strip() if res.returncode == 0 else ""
        if commits:
            task.parts["commits"] = commits
            updated = True
        dump_path = os.path.join(filepath_str, CURRENT_TASK_FILENAME)
        if os.path.exists(dump_path):
            dump = FM.load(dump_path)
            if dump.parts.get("content"):
                task.parts["notes"] = dump.parts["content"]
                updated = True

        # Detect manual unstaged or staged edits to task part files (story.md, tech.md, criteria.md, plan.md, repro.md, notes.md, etc.)
        # Compare working tree and index against HEAD for files in the task directory.
        rel_task_dir = os.path.relpath(filepath_str, self.root)
        # Unstaged changes (working tree vs index)
        res_unstaged = self._run_git(
            ["diff", "--name-only", "--", rel_task_dir], cwd=self.root
        )
        # Staged changes (index vs HEAD)
        res_staged = self._run_git(
            ["diff", "--cached", "--name-only", "--", rel_task_dir], cwd=self.root
        )
        changed_files = set()
        if res_unstaged.returncode == 0 and res_unstaged.stdout.strip():
            changed_files.update(res_unstaged.stdout.strip().splitlines())
        if res_staged.returncode == 0 and res_staged.stdout.strip():
            changed_files.update(res_staged.stdout.strip().splitlines())
        for rel_path in changed_files:
            if not rel_path.endswith(".md"):
                continue
            fname = os.path.basename(rel_path)
            if fname == CURRENT_TASK_FILENAME:
                continue
            part_name = fname[:-3]  # strip .md extension
            abs_path = os.path.join(self.root, rel_path)
            try:
                with open(abs_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if task.parts.get(part_name) != content:
                    task.parts[part_name] = content
                    updated = True
            except Exception:
                pass

        return updated

    def _get_default_branch(self):
        for b in ["main", "master"]:
            if self._run_git(["rev-parse", "--verify", b]).returncode == 0:
                return b
    def link(self, filename, blocked_by_filename):
        from .commands import link as link_cmd
        link_cmd.run(self, filename, blocked_by_filename)

        return "main"


        if os.path.abspath(f1_str) == os.path.abspath(f2_str):
            self.error("Cannot link a task to itself.")

        f1_fname = os.path.basename(f1_str)
        f2_fname = os.path.basename(f2_str)

        task = FM.load(f1_str)
        task_title = str(task.metadata.get("Ti", ""))
        task_id_num = str(task.metadata.get("Id", ""))
        tt, _ = self._parse_filename(f1_fname)
        bl = task.metadata.get("Bl", [])
        if not isinstance(bl, list):
            bl = []
        b_name = f2_fname
        b_task = FM.load(f2_str)
        b_title = str(b_task.metadata.get("Ti", ""))
        b_id = str(b_task.metadata.get("Id", ""))
        b_tt, _ = self._parse_filename(f2_fname)

        # Check for circular dependency
        if self._has_path(b_id, task_id_num):
            self.error(
                f"Circular dependency detected: linking '{filename}' -> '{blocked_by_filename}' "
                f"would create a cycle. Task {b_id} already depends on task {task_id_num}."
            )

        if b_name not in bl:
            bl.append(b_name)
            task.metadata["Bl"] = bl
            self._atomic_write(f1_str, task)
            self._append_log(f1_str, "Lk")
            self._run_git(["add", "--all"], cwd=self.tasks_path)
            self._run_git(
                ["commit", "--allow-empty", "-m", f"Lk {filename}->{b_name}"],
                cwd=self.tasks_path,
            )
            self.log(
                f"Linked: [{task_id_num}] {tt} | {task_title} -> [{b_id}] {b_tt} | {b_title}"
            )
        self.finish(
            {
                "id": task_id_num,
                "task_id": filename,
                "title": task_title,
                "linked_to": b_name,
                "linked_to_title": b_title,
            }
        )

    def move(self, filename, new_status, yes=False):
        from .commands import move as move_cmd
        move_cmd.run(self, filename, new_status, yes=yes)

    def _move_logic(self, filename, new_status, force=False, yes=False, sync=True):
        from .commands import move as move_cmd
        move_logic = getattr(move_cmd, "move_logic")
        move_logic(self, filename, new_status, force=force, yes=yes, sync=sync)

    def current(self, filename=None):
        from .commands import current as current_cmd
        current_cmd.run(self, filename=filename)

    def show(self, filename, section=None):
        from .commands import show as show_cmd
        show_cmd.run(self, filename, section=section)

    def list(self, show_all=False):
        from .commands import list as list_cmd
        list_cmd.run(self, show_all=show_all)

    def reconcile(self, target=None, all=False):
        if not target and not all:
            self.cleanup(dry_run=True)
        elif all:
            self.cleanup(yes=True)
        else:
            filepath, _ = self.find_task(target)
            if filepath:
                self._move_logic(target, "ARCHIVED", force=True)

    def _reconcile_scan(self):
        candidates = []
        for state, folder in STATE_FOLDERS.items():
            if state in ("ARCHIVED", "REJECTED", "BACKLOG"):
                continue
            fp = os.path.join(self.tasks_path, folder)
            if not os.path.exists(fp):
                continue
            for item in os.listdir(fp):
                if item == ".gitkeep":
                    continue
                path = os.path.join(fp, item)
                if not os.path.isdir(path):
                    continue
                task = FM.load(path)
                task_id = task.metadata.get("Id")
                if not task_id:
                    continue
                branch = item
                main_sha_res = self._run_git(["rev-parse", "main"])
                main_sha = (
                    main_sha_res.stdout.strip() if main_sha_res.returncode == 0 else ""
                )
                if not main_sha:
                    continue
                branch_sha_res = self._run_git(["rev-parse", branch])
                branch_sha = (
                    branch_sha_res.stdout.strip()
                    if branch_sha_res.returncode == 0
                    else ""
                )
                if not branch_sha:
                    continue
                merge_base = self._run_git(
                    ["merge-base", branch_sha, "main"]
                ).stdout.strip()
                if merge_base == main_sha:
                    candidates.append(
                        {
                            "id": task_id,
                            "task_id": task_id,
                            "title": task.metadata.get("Ti", ""),
                            "branch": branch,
                            "filepath": path,
                        }
                    )

        if not candidates:
            if self.as_json:
                self.finish({"candidates": [], "count": 0})
            else:
                print("No archive candidates found.")
            return

        if self.as_json:
            self.finish({"candidates": candidates, "count": len(candidates)})
        else:
            print(f"\nFound {len(candidates)} archive candidates:\n")
            print(f"{'#':>3} {'State':<12} {'Title':<40} {'Branch'}")
            print("-" * 80)
            for c in candidates:
                title = c["title"][:38] if len(c["title"]) > 38 else c["title"]
                print(f"{c['id']:>3} {c['state']:<12} {title:<40} {c['branch']}")
            print("\nTo archive a task, run: tasks reconcile <id>")
            print("To archive all, run: tasks reconcile --all")

    def _reconcile_archive_all(self):
        candidates = []
        for state, folder in STATE_FOLDERS.items():
            if state in ("ARCHIVED", "REJECTED", "BACKLOG"):
                continue
            fp = os.path.join(self.tasks_path, folder)
            if not os.path.exists(fp):
                continue
            for item in os.listdir(fp):
                if item == ".gitkeep":
                    continue
                path = os.path.join(fp, item)
                if not os.path.isdir(path):
                    continue
                task = FM.load(path)
                task_id = task.metadata.get("Id")
                if not task_id:
                    continue
                branch = item
                main_sha_res = self._run_git(["rev-parse", "main"])
                main_sha = (
                    main_sha_res.stdout.strip() if main_sha_res.returncode == 0 else ""
                )
                if not main_sha:
                    continue
                branch_sha_res = self._run_git(["rev-parse", branch])
                branch_sha = (
                    branch_sha_res.stdout.strip()
                    if branch_sha_res.returncode == 0
                    else ""
                )
                if not branch_sha:
                    continue
                merge_base = self._run_git(
                    ["merge-base", branch_sha, "main"]
                ).stdout.strip()
                if merge_base == main_sha:
                    candidates.append(
                        {
                            "id": task_id,
                            "task_id": task_id,
                            "title": task.metadata.get("Ti", ""),
                            "branch": branch,
                            "filepath": path,
                        }
                    )

        if not candidates:
            if self.as_json:
                self.finish({"archived": 0, "count": 0})
            else:
                print("No candidates to archive.")
            return

        archived = 0
        for c in candidates:
            self._move_logic(c["branch"], "ARCHIVED", force=True, yes=True)
            archived += 1
            if not self.as_json:
                print(f"Archived: [{c['id']}] {c['title']}")

        if self.as_json:
            self.finish({"archived": archived, "count": len(candidates)})

    def _reconcile_single(self, filename):
        filepath, state = self.find_task(filename)
        if not filepath:
            self.error(
                f"Task '{filename}' not found.",
                hint="Use 'hammer tasks list' to see available task Ids and filenames.",
            )
        task = FM.load(filepath)
        task_id = os.path.basename(filepath).rsplit(".", 1)[0]
        title = task.metadata.get("Ti", "")
        branch = task_id

        # Check if remote 'origin' exists
        has_origin = self._run_git(["remote", "get-url", "origin"]).returncode == 0
        if has_origin:
            if self._run_git(["ls-remote", "--heads", "origin", branch]).stdout:
                return
            if not self.as_json:
                print(f"Branch: {branch} (no longer exists in remote)")
        else:
            # If no origin, check if local branch exists
            has_local = self._run_git(["rev-parse", "--verify", branch]).returncode == 0
            if has_local:
                return
            if not self.as_json:
                print(f"Branch: {branch} (does not exist locally)")

        if not self.as_json:
            print(f"Task: [{task.metadata.get('Id', '')}] {title}")
            print(f"State: {state}")

        do_archive = False
        if self.as_json:
            do_archive = True
        else:
            if input("Archive this task? [y/N]: ").strip().lower() == "y":
                do_archive = True

        if do_archive:
            self._move_logic(
                os.path.basename(filepath), "ARCHIVED", force=True, yes=False
            )
            if self.as_json:
                self.finish({"archived": True, "task_id": task_id})
            else:
                print(f"Archived: [{task.metadata.get('Id', '')}] {title}")
        else:
            if self.as_json:
                self.finish({"archived": False, "task_id": task_id})
            else:
                print("Cancelled.")

    def cleanup(self, dry_run=False, yes=False):
        from .commands import cleanup as cleanup_cmd
        cleanup_cmd.run(self, dry_run=dry_run, yes=yes)
            # Respect workflow gates: only clean up branches for DONE, DONE, or REJECTED tasks
            # (ARCHIVED tasks should also be cleaned up - they completed the pipeline)

        if action == "detect":
            detected = self._detect_tools()
            if save and detected:
                cfg = load_config()
                for k, v in detected.items():
                    key_name = (
                        f"repo.{k}"
                        if k in ["lint", "test", "type_check", "format"]
                        else k
                    )
                    if v:
                        cfg[key_name] = v
                save_config(cfg)
                if self.as_json:
                    self.finish({"detected": detected, "saved": True})
                else:
                    print("Configuration saved.")
            elif self.as_json:
                self.finish({"detected": detected})
            return

        cfg = load_config()

        if action == "list":
            if self.as_json:
                self.finish(cfg)
            else:
                if cfg:
                    print("Configuration:")
                    for k, v in cfg.items():
                        print(f"  {k} = {v}")
                else:
                    print("No configuration found.")
                print("\nRun 'config detect' to auto-detect project tools.")
        elif action == "get":
            if not key:
                self.error("Missing config key.")
            if self.as_json:
                self.finish({"key": key, "value": cfg.get(key)})
            else:
                print(cfg.get(key, ""))
        elif action == "set":
            if not key or value is None:
                self.error("Missing config key or value.")
            if key not in ALLOWED_CONFIG_KEYS:
                self.error(
                    f"Invalid config key '{key}'.",
                    hint=f"Allowed keys: {', '.join(sorted(ALLOWED_CONFIG_KEYS))}. Use 'hammer tasks config detect' to auto-detect tools.",
                )
            cfg[key] = value
            save_config(cfg)
            if self.as_json:
                self.finish({"key": key, "value": value})
            else:
                print(f"Set {key} = {value}")
        else:
            if self.as_json:
                self.finish({"actions": ["get", "set", "list", "detect"]})
            else:
                print("Usage: tasks config [get|set|list|detect] [key] [value]")
                print("  get <key>     - Get config value")
                print("  set <key> <val> - Set config value")
                print("  list          - List all config")
                print("  detect        - Detect project tools and create config")

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

    def _get_config(self, key=None):
        """Load config and optionally get a specific key."""
        config_path = os.path.join(self.tasks_path, "config.yaml")
        if os.path.exists(config_path):
            try:
                import yaml

                with open(config_path, "r") as f:
                    cfg = yaml.safe_load(f) or {}
            except Exception:
                cfg = {}
        else:
            cfg = {}

        if key:
            return cfg.get(key)
        return cfg

    def get_tool(self, tool_type):
        """Get the configured tool for a given type (lint, test, type_check, format)."""
        key_map = {
            "lint": "repo.lint",
            "test": "repo.test",
            "type_check": "repo.type_check",
            "format": "repo.format",
        }
        config_key = key_map.get(tool_type)
        if config_key:
            return self._get_config(config_key)
        return None

    def run_tool(self, tool_name=None, fix=False):
        """Run configured tools (lint, test, typecheck, format)."""
        root_str = cast(str, self.root)
        check_py = os.path.join(root_str, "check.py")
        if not os.path.exists(check_py):
            self.error("check.py not found in project root.")
            return 1

        cmd = [sys.executable, check_py, tool_name or "all"]
        if fix:
            cmd.append("--fix")
        if self.as_json:
            cmd.append("--json")

        # Run check.py and capture output to pass it through TasksCLI's finish/error
        result = subprocess.run(cmd, cwd=self.root, capture_output=True, text=True)

        if self.as_json:
            try:
                data = json.loads(result.stdout)
                if result.returncode == 0:
                    self.finish(data)
                else:
                    # In JSON mode, check.py outputs success: False
                    print(result.stdout)
                    sys.exit(1)
            except json.JSONDecodeError:
                self.error(
                    f"Validation failed with exit code {result.returncode}\n{result.stdout}\n{result.stderr}"
                )
        else:
            # In plain mode, check.py prints directly to stdout/stderr
            print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            if result.returncode != 0:
                sys.exit(result.returncode)

        return result.returncode

    def undo(self, filename):
        """Undo the last operation on a task by restoring previous state from git."""
        filepath, current_state = self.find_task(filename)
        if not filepath:
            self.error(
                f"Task '{filename}' not found.",
                hint="Use 'hammer tasks list' to see all available task filenames/IDs.",
            )

        filepath_str = cast(str, filepath)
        task = FM.load(filepath_str)
        fname = os.path.basename(filepath_str)
        task_id = fname.rsplit(".", 1)[0]
        tt, _ = self._parse_filename(fname)
        task_id_num = task.metadata.get("Id", "")

        all_commits = (
            self._run_git(
                ["log", "--all", "--format=%h"],
                cwd=self.tasks_path,
            )
            .stdout.strip()
            .split("\n")
        )

        prev_commit = None
        for commit in all_commits:
            if not commit:
                continue
            tree_res = self._run_git(
                ["ls-tree", "--name-only", "-r", commit],
                cwd=self.tasks_path,
            )
            if fname in tree_res.stdout:
                prev_commit = commit
                break

        if not prev_commit:
            self.error("Nothing to undo: no git history found for this task.")

        prev_prev_commit = None
        found_current = False
        for commit in all_commits:
            if not commit:
                continue
            if found_current:
                prev_prev_commit = commit
                break
            tree_res = self._run_git(
                ["ls-tree", "--name-only", "-r", commit],
                cwd=self.tasks_path,
            )
            if fname in tree_res.stdout:
                found_current = True

        if not prev_prev_commit:
            self.error(
                "Nothing to undo: this is the first commit for this task.",
                hint="Use 'git log' in .tasks to see full history.",
            )

        last_commit_msg = self._run_git(
            ["log", "-1", "--format=%s", prev_commit],
            cwd=self.tasks_path,
        ).stdout.strip()

        if last_commit_msg.startswith("Undo:"):
            self.error(
                "Cannot undo twice in a row. Already at previous state.",
                hint="Use 'hammer tasks list' to see current state, or 'git log' in .tasks to see history.",
            )

        tree_res = self._run_git(
            ["ls-tree", "--name-only", "-r", prev_prev_commit],
            cwd=self.tasks_path,
        )
        files_to_restore = [
            f for f in tree_res.stdout.strip().split("\n") if fname in f
        ]

        if not files_to_restore:
            self.error("Could not find files to restore from previous commit.")

        temp_dir = tempfile.mkdtemp(dir=self.tasks_path)
        try:
            for file_path in files_to_restore:
                if not file_path:
                    continue
                file_name = os.path.basename(file_path)
                show_res = self._run_git(
                    ["show", f"{prev_prev_commit}:{file_path}"],
                    cwd=self.tasks_path,
                )
                if show_res.returncode != 0:
                    continue

                out_path = os.path.join(temp_dir, file_name)
                with open(out_path, "w") as f:
                    f.write(show_res.stdout)

            restored_task = FM.load(temp_dir)
            prev_state = restored_task.metadata.get("St", "BACKLOG")

            target_folder = STATE_FOLDERS.get(prev_state, STATE_FOLDERS["BACKLOG"])
            target_dir = os.path.join(self.tasks_path, target_folder, fname)

            if os.path.isdir(filepath_str):
                shutil.rmtree(filepath_str)
            shutil.move(temp_dir, target_dir)
        except Exception:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise

        self._run_git(["add", "--all"], cwd=self.tasks_path)
        self._run_git(
            [
                "commit",
                "--allow-empty",
                "-m",
                f"Undo: restore {fname} to {prev_prev_commit[:7]}",
            ],
            cwd=self.tasks_path,
        )

        final_task = FM.load(target_dir)
        self._append_log(target_dir, "Und")
        self.log(
            f"Undone: [{task_id_num}] {tt} | restored to previous state ({prev_state})"
        )
        self.finish(
            {
                "id": task_id_num,
                "task_id": task_id,
                "title": final_task.metadata.get("Ti", ""),
                "restored_from_commit": prev_prev_commit[:7],
                "previous_state": prev_state,
            }
        )

    def doctor(self, fix=False):
        from .commands import doctor as doctor_cmd
        doctor_cmd.run(self, fix=fix)
