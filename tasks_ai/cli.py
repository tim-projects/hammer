import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import cast

from .cli_io import error, finish, log
from .constants import (
    CURRENT_TASK_FILENAME,
    STATE_FOLDERS,
    TASKS_DIR,
    TASKS_GITIGNORE_MANAGED_LINES,
    TASKS_GITIGNORE_TEMPLATE,
)
from .context import DevRepoUnavailable, ProjectContext
from .file_manager import FM
from .git_service import GitService
from .hooks import HookRegistry
from .messages import MessageRegistry
from .pipeline import PipelineService
from .pipeline_hooks import (
    ArchivedCommitHook,
    AutoArchiveHook,
    BlockerCheckHook,
    CleanupReviewArtifactsHook,
    CleanWorkspaceHook,
    ContentSufficiencyHook,
    DoneAtHook,
    GuardGateHook,
    GuardRecordHook,
    MainBranchProtectionHook,
    PostMoveCommitHook,
    ProgressUpdateHook,
    ResearchGateHook,
    ReviewDiffHook,
    SaveProgressHook,
    TaskRepairHook,
    TestingToReviewGateHook,
    ValidationHook,
    ValidationPassedMarkHook,
    WorktreeCheckHook,
    WorktreeExistsHook,
    WorktreeSyncHook,
    WorktreeSyncOnExitTestingHook,
)
from .task_service import TaskService
from .utils import commit_task_paths, store_is_git, store_lock
from .validation import Validation


class TasksCLI:
    def __init__(self, as_json=False, command=None, quiet=False, dev=False, yes=False):
        self.as_json = as_json
        self.quiet = quiet
        self.dev = dev
        self.yes = yes
        self.output_messages = []
        self._last_move_force = False
        self.hook_registry = HookRegistry()
        self.messages = MessageRegistry()

        # Register EXIT hooks (Pre-move gates/checks)
        self.hook_registry.register_exit_hook("READY", MainBranchProtectionHook())
        self.hook_registry.register_exit_hook("READY", ResearchGateHook())
        self.hook_registry.register_exit_hook("BACKLOG", ContentSufficiencyHook())
        # Guard runs at every gate: a duplicate ID must never progress
        for state in [
            "BACKLOG",
            "READY",
            "PROGRESSING",
            "TESTING",
            "REVIEW",
            "STAGING",
            "DONE",
        ]:
            self.hook_registry.register_exit_hook(state, GuardGateHook())
        self.hook_registry.register_exit_hook("PROGRESSING", MainBranchProtectionHook())
        self.hook_registry.register_exit_hook("PROGRESSING", ValidationHook())
        self.hook_registry.register_exit_hook("PROGRESSING", ProgressUpdateHook())
        self.hook_registry.register_exit_hook("TESTING", ValidationHook())
        self.hook_registry.register_exit_hook(
            "TESTING", WorktreeSyncOnExitTestingHook()
        )
        self.hook_registry.register_exit_hook("TESTING", TestingToReviewGateHook())
        self.hook_registry.register_exit_hook("STAGING", CleanWorkspaceHook())

        # Register ENTER hooks (Post-move actions)
        self.hook_registry.register_enter_hook("BACKLOG", CleanupReviewArtifactsHook())
        self.hook_registry.register_enter_hook("READY", CleanupReviewArtifactsHook())
        self.hook_registry.register_enter_hook(
            "PROGRESSING", CleanupReviewArtifactsHook()
        )
        self.hook_registry.register_enter_hook("PROGRESSING", TaskRepairHook())
        self.hook_registry.register_enter_hook("PROGRESSING", ContentSufficiencyHook())
        self.hook_registry.register_enter_hook("PROGRESSING", BlockerCheckHook())
        self.hook_registry.register_enter_hook("PROGRESSING", WorktreeCheckHook())
        self.hook_registry.register_enter_hook("PROGRESSING", WorktreeSyncHook())
        self.hook_registry.register_enter_hook("TESTING", WorktreeExistsHook())
        self.hook_registry.register_enter_hook("TESTING", ValidationPassedMarkHook())
        self.hook_registry.register_enter_hook("REVIEW", WorktreeExistsHook())
        self.hook_registry.register_enter_hook("REVIEW", WorktreeCheckHook())
        self.hook_registry.register_enter_hook("REVIEW", ReviewDiffHook())
        self.hook_registry.register_enter_hook("STAGING", WorktreeCheckHook())
        self.hook_registry.register_enter_hook("STAGING", CleanWorkspaceHook())
        self.hook_registry.register_enter_hook("DONE", WorktreeCheckHook())
        self.hook_registry.register_enter_hook("ARCHIVED", WorktreeCheckHook())
        self.hook_registry.register_enter_hook("ARCHIVED", ArchivedCommitHook())

        # Post-move generic hooks
        self.hook_registry.register_enter_hook("DONE", DoneAtHook())
        self.hook_registry.register_enter_hook("DONE", AutoArchiveHook())
        for state in [
            "BACKLOG",
            "READY",
            "PROGRESSING",
            "TESTING",
            "REVIEW",
            "STAGING",
            "DONE",
            "REJECTED",
        ]:
            self.hook_registry.register_enter_hook(state, SaveProgressHook())
            self.hook_registry.register_enter_hook(state, PostMoveCommitHook())
            self.hook_registry.register_enter_hook(state, GuardRecordHook())

        try:
            self.context = ProjectContext(dev=dev)
        except DevRepoUnavailable as exc:
            # Refuse: falling back to the real repo is the bug dev mode exists to avoid.
            self.error(
                "DEV_REPO_UNAVAILABLE", detail=str(exc), command=command or "tasks"
            )
        self.root = self.context.repo_root or os.getcwd()

        self.git = GitService(self.context, logger=self)
        self.pipeline = PipelineService(self.git, logger=self)
        self.validation = Validation(self)
        self.task_service = TaskService(self)

        install_dir = Path(__file__).resolve().parent.parent
        self.repo_script = str(install_dir / "repo.py")

        self.tasks_dir = TASKS_DIR
        canonical_store = os.path.realpath(
            os.path.join(self.context.main_repo_root, TASKS_DIR)
        )

        def resolve_store_path(value):
            if os.path.isabs(value):
                return os.path.realpath(value)
            return os.path.realpath(os.path.join(self.context.main_repo_root, value))

        if not dev:
            pyproject_path = self.context.resolve_path("pyproject.toml")
            if os.path.exists(pyproject_path):
                try:
                    import toml

                    with open(pyproject_path, "r") as f:
                        pyproject_data = toml.load(f)
                        configured = (
                            pyproject_data.get("tool", {})
                            .get("tasks_ai", {})
                            .get("tasks_dir", self.tasks_dir)
                        )
                    resolved = resolve_store_path(str(configured))
                    if resolved != canonical_store:
                        self.error("STORE_NOT_CENTRAL", store_path=resolved)
                    self.tasks_dir = str(configured)
                except Exception:  # noqa: BLE001, S110
                    pass

        self.context.tasks_path = canonical_store
        if dev or os.environ.get("HAMMER_DEV_TASKS_DIR"):
            self.context.tasks_path = os.environ.get(
                "HAMMER_DEV_TASKS_DIR", "/tmp/.tasks"
            )
            if not os.path.exists(self.context.tasks_path):
                os.makedirs(self.context.tasks_path, exist_ok=True)

        self.tasks_path = self.context.tasks_path

        if not self.tasks_path:
            # Never invent a store: an unresolvable path would silently create
            # one wherever the command happens to run.
            self.error("STORE_NOT_CENTRAL")

        # Production has exactly one store. Read its config from the canonical
        # path, then reject any override that resolves elsewhere.
        cfg = self._get_config()
        self.log(f"DEBUG: Loading config from {self.tasks_path}")
        if (
            not dev
            and not os.environ.get("HAMMER_DEV_TASKS_DIR")
            and cfg
            and isinstance(cfg, dict)
            and cfg.get("tasks_dir")
        ):
            td = str(cfg["tasks_dir"])
            resolved = resolve_store_path(td)
            if resolved != canonical_store:
                self.error("STORE_NOT_CENTRAL", store_path=resolved)
            self.tasks_dir = td
            self.tasks_path = canonical_store
            self.context.tasks_path = canonical_store

        # A store resolved inside a worktree is invisible to the central store
        # and is destroyed by the next branch checkout: refuse, do not write.
        if (
            not dev
            and self.context.is_worktree
            and self._is_within(self.tasks_path, self.context.repo_root)
        ):
            self.error("STORE_NOT_CENTRAL", store_path=self.tasks_path)

        self.logs_path = os.path.join(self.tasks_path, "logs")

        if os.path.exists(self.tasks_path):
            self._migrate_live_to_done()
            if command and command != "delete":
                self._clear_delete_marks()

    @staticmethod
    def _is_within(path, directory):
        """True when path is directory itself or lives under it."""
        path = os.path.realpath(path)
        directory = os.path.realpath(directory)
        try:
            return os.path.commonpath([path, directory]) == directory
        except ValueError:
            return False  # different drives: never inside

    # --- CLI IO ---
    def log(self, message):
        log(self, message)

    def console(self, type_tag, action, result):
        """Standardized, concise logging: [type] action -> result."""
        log(self, f"[{type_tag.lower()}] {action.lower()} -> {result.lower()}")

    def error(self, code, hint_code=None, **kwargs):
        message = self.messages.get_error(code, **kwargs)
        hint = self.messages.get_hint(hint_code or code, **kwargs)
        error(self, message, hint=hint if hint else None)

    def finish(self, data=None):
        finish(self, data=data)

    # --- Service Delegation ---
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
                    # Preserve existing sibling files/folders if they exist
                    if os.path.isdir(path):
                        for item in os.listdir(path):
                            src_item = os.path.join(path, item)
                            dst_item = os.path.join(temp_dir, item)
                            if os.path.isdir(src_item):
                                shutil.copytree(src_item, dst_item)
                            else:
                                shutil.copy2(src_item, dst_item)

                    FM.dump(task_or_content, temp_dir)
                    if os.path.exists(path):
                        if os.path.isdir(path):
                            shutil.rmtree(path)
                        else:
                            os.remove(path)
                    os.rename(temp_dir, path)
                except Exception:
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)
                    raise
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
            except Exception:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                raise

    def _append_log(self, path, message, section="progress"):
        FM.append_log(path, message, section=section)
        if path:
            # FM.append_log writes the section file (progress.md by default), not
            # a separate activity.log: staging the wrong name fails silently and
            # the log line never reaches the store.
            rel_log = os.path.join(
                os.path.relpath(path, self.tasks_path), f"{section}.md"
            )
            if store_is_git(self):
                self._run_git(["add", rel_log], cwd=self.tasks_path)

    def _run_git(self, cmd, cwd=None, check=False):
        return self.git.run(cmd, cwd=cwd, check=check)

    def _get_default_branch(self):
        return self.git.get_default_branch()

    def _generate_review_diff(self, task_path, branch):
        return self.git.generate_review_diff(task_path, branch)

    def _push_tasks_branch(self, branch="tasks", fatal=True):
        return self.git.push_tasks_branch(branch=branch, fatal=fatal)

    def _git_merge_transition(self, task, target_state, yes=False, force=False):
        return self.pipeline.git_merge_transition(
            task, target_state, yes=yes, force=force
        )

    def _validate_pipeline_gate(self, task, target_state, task_path=None):
        if not task_path:
            task_id = str(task.metadata.get("Id"))
            task_path, _ = self.find_task(task_id)
        if not task_path:
            return
        try:
            return self.pipeline.validate_gate(self, task, target_state, task_path)
        except Exception as e:  # noqa: BLE001
            if hasattr(e, "code"):
                self.error(e.code, **e.kwargs)
            else:
                self.error(str(e))
            sys.exit(1)

    def _detect_tools(self):
        return self.validation.detect_tools()

    def _validate_path(self, path):
        return self.validation.validate_path(path)

    def run_tool(self, tool_name=None, fix=False):
        return self.validation.run_tool(tool_name=tool_name, fix=fix)

    def find_task(self, filename):
        return self.task_service.find_task(filename)

    def get_active_task(self, filename=None):
        return self.task_service.get_active_task(filename=filename)

    def processing_candidates(self):
        return self.task_service.processing_candidates()

    def _get_next_id(self):
        from .counter import TaskCounterProtector

        protector = TaskCounterProtector(self.tasks_path, self)
        return protector.get_next_id(self)

    def _migrate_live_to_done(self):
        """Migrate .tasks/live to .tasks/done if it exists."""
        live_dir = os.path.join(self.tasks_path, "live")
        done_dir = os.path.join(self.tasks_path, "done")

        if os.path.exists(live_dir):
            items = [i for i in os.listdir(live_dir) if i != ".gitkeep"]
            if items:
                self.log(f"Migrating {len(items)} tasks from LIVE to DONE...")
                os.makedirs(done_dir, exist_ok=True)
                for item in items:
                    src = os.path.join(live_dir, item)
                    dst = os.path.join(done_dir, item)
                    if os.path.exists(os.path.join(self.tasks_path, ".git")):
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

                if os.path.exists(os.path.join(self.tasks_path, ".git")):
                    # Whole-store sweep by nature (every LIVE record moves), so it
                    # cannot be scoped per task; the store lock at least keeps
                    # another agent's commit from landing inside this commit.
                    with store_lock(self):
                        self._run_git(["add", "--all"], cwd=self.tasks_path)
                        self._run_git(
                            ["commit", "-m", "Migrate LIVE tasks to DONE"],
                            cwd=self.tasks_path,
                        )
                self.log("Migration complete.")

            remaining = os.listdir(live_dir)
            if not remaining or (len(remaining) == 1 and remaining[0] == ".gitkeep"):
                try:
                    if os.path.exists(os.path.join(self.tasks_path, ".git")):
                        self._run_git(["rm", "-rf", "live"], cwd=self.tasks_path)
                    if os.path.exists(live_dir):
                        shutil.rmtree(live_dir)
                except Exception:  # noqa: BLE001, S110
                    pass

    def _clear_delete_marks(self):
        updated = False
        for folder in STATE_FOLDERS.values():
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
                except Exception as e:  # noqa: BLE001
                    self.log(f"Warning: Failed to load task at {path}: {e}")
        if updated and store_is_git(self):
            # Whole-store sweep by nature (a mark can sit in any state folder), so
            # it cannot be scoped per task; the store lock at least keeps another
            # agent's commit from landing inside this commit.
            with store_lock(self):
                self._run_git(["add", "--all"], cwd=self.tasks_path)
                self._run_git(
                    ["commit", "--allow-empty", "-m", "Clear delete marks"],
                    cwd=self.tasks_path,
                )

    def _validate_task_id(self, task_id):
        if not task_id:
            return False
        return bool(re.match(r"^[a-zA-Z0-9\-_.]+$", task_id))

    def _run_repo(self, args, cwd=None):
        cwd = cwd or self.root
        repo_path = os.path.join(self.root, "repo")
        if not os.path.exists(repo_path):
            repo_path = self.repo_script
        result = subprocess.run(  # noqa: PLW1510
            [repo_path] + args, cwd=cwd, capture_output=True, text=True
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

    def _auto_archive(self):
        for state in ["DONE"]:
            folder = STATE_FOLDERS.get(state)
            if not folder:
                continue
            target_dir = os.path.join(self.tasks_path, folder)
            if not os.path.exists(target_dir):
                continue
            now = datetime.now()  # noqa: DTZ005
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
                                    done_date = datetime.strptime(  # noqa: DTZ007
                                        match.group(1), "%y%m%d %H:%M"
                                    )
                                    break
                        if done_date and (now - done_date) > timedelta(days=7):
                            self.log(f"Auto-archiving: {item}")
                            self._move_logic(item, "ARCHIVED", force=True, yes=False)

    def _get_config(self, key=None):
        from .constants import load_config

        cfg = load_config(self.tasks_path)
        if key:
            return cfg.get(key)
        return cfg

    def get_tool(self, tool_type):
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

    def _sync_task_content(self, filepath, task, is_final=False):
        if not filepath:
            return False
        filepath_str = cast(str, filepath)
        tn = os.path.basename(filepath_str)
        _, branch = self._parse_filename(tn)
        updated = False
        default_branch = self._get_default_branch()
        res = (
            self._run_git(["log", branch, f"^{default_branch}", "--oneline"])
            if default_branch
            else None
        )
        commits = res.stdout.strip() if res and res.returncode == 0 else ""
        if commits:
            task.parts["commits"] = commits
            updated = True

        dump_path = os.path.join(filepath_str, CURRENT_TASK_FILENAME)
        if os.path.exists(dump_path):
            dump = FM.load(dump_path)
            if dump.parts.get("content"):
                task.parts["notes"] = dump.parts["content"]
                updated = True
        return updated

    def _has_path(self, start_id, target_id, visited=None):
        if visited is None:
            visited = set()
        if start_id in visited:
            return False
        visited.add(start_id)

        filepath, _ = self.find_task(str(start_id))
        if not filepath:
            return False

        try:
            task = FM.load(filepath)
            bl = task.metadata.get("Bl", [])
            if not isinstance(bl, list):
                bl = []
            for blocker_dir in bl:
                blocker_id = (
                    blocker_dir.split("-")[0] if "-" in blocker_dir else blocker_dir
                )
                if str(blocker_id) == str(target_id):
                    return True
                if self._has_path(blocker_id, target_id, visited):
                    return True
        except Exception:  # noqa: BLE001, S110
            pass
        return False

    # --- Commands ---
    def init_hooks(self):
        self.log("Installing git hooks...")
        self.install_hooks()
        self.log("✅ Git hooks installed.")

    def _resolve_hooks_dir(self):
        """The COMMON hooks dir. Inside a task worktree `.git` is a file, so
        `<root>/.git/hooks` silently misses; git resolves the shared dir."""
        result = self._run_git(["rev-parse", "--git-path", "hooks"], cwd=self.root)
        candidates = []
        if result.returncode == 0:
            path = result.stdout.strip()
            if path:
                candidates.append(os.path.join(self.root, path))
        candidates.append(os.path.join(self.root, ".git", "hooks"))
        for candidate in candidates:
            if os.path.isdir(candidate):
                return candidate
        return None

    def install_hooks(self):
        hook_dir = self._resolve_hooks_dir()
        if not hook_dir:
            return

        # The hooks must target the repo's actual default branch, not assume
        # 'main': same resolution as GitService.get_default_branch (origin/HEAD,
        # then the first existing of main/master, with main as final fallback).
        default_branch_snippet = (
            "default_branch=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null)\n"
            'if [ -z "$default_branch" ]; then\n'
            "    if git rev-parse --verify --quiet main >/dev/null; then default_branch=main\n"
            "    elif git rev-parse --verify --quiet master >/dev/null; then default_branch=master\n"
            "    else default_branch=main\n"
            "    fi\n"
            "fi"
        )

        # pre-commit hook
        with open(os.path.join(hook_dir, "pre-commit"), "w") as f:
            f.write(
                f'#!/bin/bash\n\ntarget_branch=$(git rev-parse --abbrev-ref HEAD)\n{default_branch_snippet}\n\n# Allow the default branch plus the pipeline branches\nif [[ "$target_branch" == "$default_branch" || "$target_branch" == "staging" || "$target_branch" == "testing" ]]; then\n    exit 0\nfi\n\n# Block non-conformant branch names\n# Convention: <id>-<type>-<title>\nif [[ ! "$target_branch" =~ ^[0-9]+-(task|issue|docs)-[a-zA-Z0-9-]+$ ]]; then\n    echo "❌ Branch name \'$target_branch\' does not conform to convention: <id>-<type>-<title>."\n    echo "Use \'hammer tasks create\' to create a conformant feature branch."\n    exit 1\nfi'
            )
        os.chmod(os.path.join(hook_dir, "pre-commit"), 0o755)

        # pre-merge-commit hook (git-merge invokes this before a merge commit;
        # 'pre-merge' is not a git hook name and would never run)
        with open(os.path.join(hook_dir, "pre-merge-commit"), "w") as f:
            f.write(
                f'#!/bin/bash\n\n# hammer\'s own pipeline/repo merges set this; only raw user merges are blocked\nif [ "$HAMMER_INTERNAL_CALL" == "1" ]; then\n    exit 0\nfi\n\ntarget_branch=$(git rev-parse --abbrev-ref HEAD)\n{default_branch_snippet}\nif [ "$target_branch" == "$default_branch" ]; then\n    echo "⚠️  Direct git merge into $default_branch detected. Pipeline governance requires \'./hammer repo merge\'. Aborting."\n    exit 1\nfi'
            )
        os.chmod(os.path.join(hook_dir, "pre-merge-commit"), 0o755)

        # post-merge hook
        with open(os.path.join(hook_dir, "post-merge"), "w") as f:
            f.write(
                f'#!/bin/bash\n\nif [ "$HAMMER_INTERNAL_MERGE" == "1" ]; then\n    exit 0\nfi\n\ntarget_branch=$(git rev-parse --abbrev-ref HEAD)\n{default_branch_snippet}\nif [ "$target_branch" == "$default_branch" ]; then\n    echo "Checking pipeline sync..."\n    staging_diff=$(git log $default_branch..staging --oneline)\n    testing_diff=$(git log staging..testing --oneline)\n    if [ -n "$staging_diff" ] || [ -n "$testing_diff" ]; then\n        echo "⚠️  Pipeline branches (staging/testing) are out of sync with $default_branch!"\n        echo "Run \'./hammer repo sync\' to reconcile."\n    else\n        echo "✅ Pipeline branches are in sync."\n    fi\nfi'
            )
        os.chmod(os.path.join(hook_dir, "post-merge"), 0o755)

        # pre-receive hook
        with open(os.path.join(hook_dir, "pre-receive"), "w") as f:
            f.write(
                f'#!/bin/bash\n\n{default_branch_snippet}\n\nwhile read oldrev newrev refname; do\n    if [[ "$newrev" == "0000000000000000000000000000000000000000" ]]; then\n        branch=$(basename "$refname")\n        if [[ "$branch" == "$default_branch" || "$branch" == "staging" || "$branch" == "testing" ]]; then\n            echo "❌ Cannot delete critical pipeline branch: $branch"\n            exit 1\n        fi\n    fi\ndone'
            )
        os.chmod(os.path.join(hook_dir, "pre-receive"), 0o755)

    def _backup_tasks_directory(self, tasks_path):
        from datetime import datetime, timezone

        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M-%S")
        backup_dir = os.path.join(os.path.dirname(tasks_path), ".tasks.backup")
        backup_path = os.path.join(backup_dir, timestamp, ".tasks")
        self.log(f"Backing up existing tasks to {backup_path}...")
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        if os.path.exists(backup_path):
            shutil.rmtree(backup_path)
        shutil.copytree(tasks_path, backup_path)
        return backup_path

    def _ensure_tasks_backup_gitignored(self):
        gitignore_path = os.path.join(self.root, ".gitignore")
        ignore_line = "/.tasks.backup/"
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r") as f:
                content = f.read()
            if ignore_line not in content:
                with open(gitignore_path, "a") as f:
                    f.write(f"\n{ignore_line}\n")
        else:
            with open(gitignore_path, "w") as f:
                f.write(f"{ignore_line}\n")

    def _ensure_tasks_store_gitignore(self):
        """Reconcile the task store's managed ignore rules in place."""
        gitignore_path = os.path.join(self.tasks_path, ".gitignore")
        existing = ""
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r") as f:
                existing = f.read()

        preserved = []
        for line in existing.splitlines():
            stripped = line.strip()
            if not stripped or stripped in TASKS_GITIGNORE_MANAGED_LINES:
                continue
            preserved.append(line)

        content = TASKS_GITIGNORE_TEMPLATE
        if preserved:
            content += "\n# User-authored entries\n" + "\n".join(preserved) + "\n"
        if content == existing:
            return False
        with open(gitignore_path, "w") as f:
            f.write(content)
        return True

    def _commit_tasks_store_gitignore(self):
        if not self._ensure_tasks_store_gitignore():
            return
        self._run_git(["add", "--", ".gitignore"], cwd=self.tasks_path)
        commit = self._run_git(
            ["commit", "-m", "Update tasks gitignore"], cwd=self.tasks_path
        )
        if commit.returncode != 0:
            self.error(
                "STORE_WRITE_FAIL",
                hint=(commit.stderr or "").strip() or "git commit failed",
            )

    def init(self, force=False):
        if not force and os.path.isdir(os.path.join(self.tasks_path, ".git")):
            self._commit_tasks_store_gitignore()

        if self.dev:
            # Every dev command pre-creates the store directory, so bare
            # existence proves nothing: a fresh path must still initialize.
            # A store counts as initialized only by content init itself wrote --
            # its git repo, or task records a plain directory never gets.
            initialized = os.path.isdir(
                os.path.join(self.tasks_path, ".git")
            ) or self._tasks_directory_has_data(self.tasks_path)
            if initialized:
                if not force:
                    self.error("Dev tasks already initialized. Use --force to reset.")
                else:
                    self._backup_tasks_directory(self.tasks_path)
                    self.log(f"Resetting dev tasks at {self.tasks_path}")
                    shutil.rmtree(self.tasks_path)

            from .constants import TASKS_BRANCH

            clone_result = self._run_git(
                [
                    "clone",
                    "--branch",
                    TASKS_BRANCH,
                    "--depth",
                    "1",
                    self.context.invoked_repo_root or self.root,
                    self.tasks_path,
                ],
                check=False,
            )
            if clone_result.returncode != 0:
                self.error(
                    f"Failed to clone tasks branch '{TASKS_BRANCH}' from parent repo. "
                    "Ensure the branch exists and the parent repo is a valid git repository."
                )
            if self.dev:
                # Cloning sets origin to the invoked repo; a dev store must carry
                # no remote at all, so no dev command can push anywhere.
                self._run_git(["remote", "remove", "origin"], cwd=self.tasks_path)
            self._commit_tasks_store_gitignore()

            for folder in STATE_FOLDERS.values():
                p = os.path.join(self.tasks_path, folder)
                os.makedirs(p, exist_ok=True)
                Path(os.path.join(p, ".gitkeep")).touch()
            counter_file = os.path.join(self.tasks_path, ".task_counter")
            if not os.path.exists(counter_file):
                with open(counter_file, "w") as f:
                    f.write("0")
                self._run_git(["add", "."], cwd=self.tasks_path)
                self._run_git(
                    ["commit", "-m", "Init task counter"], cwd=self.tasks_path
                )
            self._ensure_tasks_backup_gitignored()
            self.log(f"Dev tasks initialized at {self.tasks_path}")
            self.finish()
            return

        # Non-dev (production) storage path
        if not force and os.path.exists(self.tasks_path):
            self.error("Tasks already initialized. Use --force to backup and reset.")
        elif force and os.path.exists(self.tasks_path):
            self._backup_tasks_directory(self.tasks_path)

            if os.path.isdir(self.tasks_path):
                shutil.rmtree(self.tasks_path)
            else:
                os.remove(self.tasks_path)

        # Regular init
        original_branch = self._run_git(["branch", "--show-current"]).stdout.strip()
        from .constants import TASKS_BRANCH

        branches = self._run_git(["branch"]).stdout
        if TASKS_BRANCH not in branches:
            self._run_git(["checkout", "--orphan", TASKS_BRANCH])
            self._run_git(["reset", "--hard"])
            self._run_git(["commit", "--allow-empty", "-m", "Initial tasks commit"])
            if original_branch:
                self._run_git(["checkout", original_branch])
            else:
                self._run_git(["checkout", "-"])

        gitignore_path = os.path.join(self.root, ".gitignore")
        ignore_line = f"/{self.tasks_dir}/"
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r") as f:
                content = f.read()
            if ignore_line not in content:
                with open(gitignore_path, "a") as f:
                    f.write(f"\n{ignore_line}\n")
        else:
            with open(gitignore_path, "w") as f:
                f.write(f"{ignore_line}\n")

        self._ensure_tasks_backup_gitignored()

        self._run_git(["rm", "-rf", "--cached", self.tasks_dir], cwd=self.root)

        if os.path.exists(self.tasks_path):
            print(f"DEBUG: Has data: {self._tasks_directory_has_data(self.tasks_path)}")
            if self._tasks_directory_has_data(self.tasks_path):
                self._backup_tasks_directory(self.tasks_path)
                if not force:
                    self.error(
                        "Found existing .tasks directory with data. Use --force to reset."
                    )
            if os.path.isdir(self.tasks_path):
                shutil.rmtree(self.tasks_path)
            else:
                os.remove(self.tasks_path)

        clone_result = self._run_git(
            [
                "clone",
                "--branch",
                TASKS_BRANCH,
                "--depth",
                "1",
                self.root,
                self.tasks_path,
            ],
            check=False,
        )
        if clone_result.returncode != 0:
            self.error(
                f"Failed to clone tasks branch '{TASKS_BRANCH}' from parent repo. "
                "Ensure the branch exists and the parent repo is a valid git repository."
            )
        self._commit_tasks_store_gitignore()

        for folder in STATE_FOLDERS.values():
            p = os.path.join(self.tasks_path, folder)
            if not os.path.exists(p):
                os.makedirs(p)
                Path(os.path.join(p, ".gitkeep")).touch()
                self._run_git(
                    ["add", os.path.join(folder, ".gitkeep")], cwd=self.tasks_path
                )

        if self._run_git(["status", "--porcelain"], cwd=self.tasks_path).stdout:
            self._run_git(["commit", "-m", "Init tasks folders"], cwd=self.tasks_path)

        counter_file = os.path.join(self.tasks_path, ".task_counter")
        if not os.path.exists(counter_file):
            with open(counter_file, "w") as f:
                f.write("0")
            self._run_git(["add", ".task_counter"], cwd=self.tasks_path)
            self._run_git(["commit", "-m", "Init task counter"], cwd=self.tasks_path)

        config_file = os.path.join(self.tasks_path, "config.yaml")
        if not os.path.exists(config_file):
            # Seed only what detection actually finds. A missing key is the loud,
            # actionable path ('set repo.<key>'); a vacuous /bin/true would let the
            # gate pass without running anything.
            detected = {
                key: value
                for key, value in self._detect_tools().items()
                if key in ("lint", "test", "type_check", "format") and value
            }
            if detected:
                body = "".join(f"  {key}: {value}\n" for key, value in detected.items())
                with open(config_file, "w") as f:
                    f.write("repo:\n" + body)
                self._run_git(["add", "config.yaml"], cwd=self.tasks_path)
                self._run_git(
                    ["commit", "-m", "Init default config"], cwd=self.tasks_path
                )
            else:
                self.log(
                    "No validation tools detected. Run 'tasks config detect --save' "
                    "once you have chosen lint, test, type_check and format tools."
                )

        self.install_hooks()
        subprocess.run(  # noqa: PLW1510
            ["git", "config", "--global", "merge.message", "merge: auto-merge"],
            cwd=self.root,
        )
        os.environ["GIT_MERGE_AUTOEDIT"] = "no"
        self.log("Tasks initialized.")
        self.finish()

    def save(self, branch="tasks"):
        from .commands import save as save_cmd

        if self.dev and not self.git.dev_push_allowed():
            # Refused at the command so the agent sees the actionable error; the
            # push helper refuses again for the paths that bypass this command.
            self.error("DEV_COMMAND_REFUSED", command="./hammer tasks save")

        result = save_cmd.run(self, branch=branch, fatal=True)
        self.finish(result)

    def restore(self, branch="tasks", force=False):
        """Restore .tasks from the specified backup branch by cloning."""
        tasks_path = self.tasks_path
        if os.path.exists(tasks_path):
            if force:
                self.log(
                    f"WARNING: {tasks_path} exists. --force specified, will overwrite."
                )
                if os.path.isdir(tasks_path):
                    shutil.rmtree(tasks_path)
                else:
                    os.remove(tasks_path)
            else:
                self.error(
                    f"The directory '{tasks_path}' already exists. Use --force to overwrite, or delete it first."
                )

        remote_url = self._run_git(
            ["remote", "get-url", "origin"], cwd=self.root
        ).stdout.strip()
        if not remote_url:
            remote_url = self.root

        branch_check = self._run_git(
            ["ls-remote", "--heads", remote_url, branch], cwd=self.root
        )
        if not branch_check.stdout.strip():
            self.error(
                f"Branch '{branch}' not found at '{remote_url}'. Cannot restore."
            )

        clone_result = self._run_git(
            [
                "clone",
                "--branch",
                branch,
                "--depth",
                "1",
                remote_url,
                tasks_path,
            ],
            check=False,
        )
        if clone_result.returncode != 0:
            self.error(
                f"Failed to clone branch '{branch}' from '{remote_url}'. "
                "Ensure the branch exists and the source is a valid git repository."
            )

        self.log(f"Restored .tasks from branch '{branch}' at {tasks_path}")
        self.finish({"restored": True, "branch": branch, "path": tasks_path})

    def list(self, show_all=False):
        from .commands import list as list_cmd

        if os.path.exists(self.tasks_path):
            self._auto_archive()
        list_cmd.run(self, show_all=show_all)

    def show(self, filename, section=None, show_all=False):
        from .commands import show as show_cmd

        show_cmd.run(self, filename, section=section, show_all=show_all)

    def current(self, filename=None):
        from .commands import current as current_cmd

        current_cmd.run(self, filename)

    def checkpoint(self, filename=None):
        from .commands import checkpoint as checkpoint_cmd

        checkpoint_cmd.run(self, filename)

    def create(self, title, task_type="task", priority=None, **kwargs):
        from .commands import create as create_cmd

        create_cmd.run(self, title, task_type=task_type, priority=priority, **kwargs)

    def modify(self, filename, **kwargs):
        from .commands import modify as modify_cmd

        modify_cmd.run(self, filename, **kwargs)

    def move(self, filename, status, yes=False, force=False):
        from .commands import move as move_cmd

        move_cmd.run(self, filename, status, yes=yes, force=force)

    def delete(self, filename, confirm=None):
        from .commands import delete as delete_cmd

        delete_cmd.run(self, filename, confirm=confirm)

    def mount(self, task_id):
        from .commands import mount as mount_cmd

        mount_cmd.run(self, task_id)

    def link(self, filename, blocked_by):
        from .commands import link as link_cmd

        link_cmd.run(self, filename, blocked_by)

    def unlink(self, filename, blocked_by):
        from .commands import unlink as unlink_cmd

        unlink_cmd.run(self, filename, blocked_by)

    def reconcile(self, target=None, all=False, dry_run=False):
        if not target and not all:
            self._reconcile_scan(dry_run=dry_run)
        elif all:
            self._reconcile_archive_all(dry_run=dry_run)
        else:
            self._reconcile_single(target, dry_run=dry_run)

    def _reconcile_scan(self, dry_run=False):
        candidates = []
        all_tasks = []
        for state, folder in STATE_FOLDERS.items():
            fp = os.path.join(self.tasks_path, folder)
            if not os.path.exists(fp):
                continue
            for item in os.listdir(fp):
                if item == ".gitkeep":
                    continue
                path = os.path.join(fp, item)
                if os.path.isdir(path):
                    all_tasks.append((path, state, item))

        # Second, verify all tasks
        for path, state, item in all_tasks:
            try:
                task = FM.load(path)
                task_state = task.metadata.get(
                    "St", state
                )  # Default to folder state if St missing
                expected_folder = STATE_FOLDERS.get(task_state)
                if os.path.basename(os.path.dirname(path)) != expected_folder:
                    self.console(
                        "tamper",
                        "detected",
                        f"{item} in {os.path.basename(os.path.dirname(path))}, metadata={task_state}",
                    )
                    if not dry_run:
                        target_path = os.path.join(
                            self.tasks_path, expected_folder, item
                        )
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        shutil.move(path, target_path)
                    else:
                        self.console("tamper", "would_fix", item)
                    continue

                if task_state == "DONE":
                    # Archive scan - check worktree branch merged to the default branch
                    branch = item
                    default_branch = self._get_default_branch()
                    if not default_branch:
                        continue
                    main_sha = self._run_git(
                        ["rev-parse", default_branch], cwd=self.root
                    ).stdout.strip()
                    branch_sha = self._run_git(
                        ["rev-parse", branch], cwd=self.context.main_repo_root
                    ).stdout.strip()
                    if (
                        main_sha
                        and branch_sha
                        and self._run_git(
                            ["merge-base", branch_sha, default_branch],
                            cwd=self.context.main_repo_root,
                        ).stdout.strip()
                        == main_sha
                    ):
                        candidates.append(
                            {
                                "id": task.metadata.get("Id"),
                                "title": task.metadata.get("Ti", ""),
                                "branch": branch,
                                "filepath": path,
                                "state": "DONE",
                            }
                        )
            except Exception:  # noqa: BLE001, S112
                continue

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

    def _reconcile_archive_all(self, dry_run=False):
        candidates = []
        folder = STATE_FOLDERS.get("DONE")
        fp = os.path.join(self.tasks_path, folder)
        if not os.path.exists(fp):
            if self.as_json:
                self.finish({"archived": 0, "dry_run": dry_run})
            else:
                print(f"{'Dry-run: ' if dry_run else ''}Archived 0 tasks.")
            return
        for item in os.listdir(fp):
            if item == ".gitkeep":
                continue
            path = os.path.join(fp, item)
            if not os.path.isdir(path):
                continue
            branch = item
            try:
                default_branch = self._get_default_branch()
                if not default_branch:
                    print(
                        f"⚠️ Skipping {branch}: no default branch (main/master) found."
                    )
                    continue
                main_sha = self._run_git(
                    ["rev-parse", default_branch], cwd=self.root
                ).stdout.strip()
                branch_sha = self._run_git(
                    ["rev-parse", branch], cwd=self.context.main_repo_root
                ).stdout.strip()
                merge_base = self._run_git(
                    ["merge-base", branch_sha, default_branch],
                    cwd=self.context.main_repo_root,
                ).stdout.strip()
                if merge_base == main_sha:
                    candidates.append(item)
                else:
                    print(f"⚠️ Skipping {branch}: Not fully merged.")
            except Exception as e:  # noqa: BLE001
                print(f"⚠️ Skipping {branch}: Git check failed: {e}")
        archived = 0
        for branch in candidates:
            try:
                if not dry_run:
                    self._move_logic(branch, "ARCHIVED", force=True, yes=True)
                    archived += 1
                else:
                    self.console("archive", "would_archive", branch)
            except Exception as e:  # noqa: BLE001
                print(f"❌ Failed to archive {branch}: {e}")
        if self.as_json:
            self.finish({"archived": archived, "dry_run": dry_run})
        else:
            print(f"{'Dry-run: ' if dry_run else ''}Archived {archived} tasks.")

    def _reconcile_single(self, filename, dry_run=False):
        filepath, state = self.find_task(filename)
        if not filepath:
            self.error("TASK_NOT_FOUND", filename=filename)
        task = FM.load(filepath)
        branch = task.metadata.get("Br", "")
        if not branch:
            branch = os.path.basename(filepath).rsplit(".", 1)[0]

        has_origin = (
            self._run_git(
                ["remote", "get-url", "origin"], cwd=self.context.main_repo_root
            ).returncode
            == 0
        )
        if has_origin:
            if self._run_git(
                ["ls-remote", "--heads", "origin", branch],
                cwd=self.context.main_repo_root,
            ).stdout:
                return
        else:
            if (
                self._run_git(
                    ["rev-parse", "--verify", branch], cwd=self.context.main_repo_root
                ).returncode
                == 0
            ):
                return

        if not self.as_json:
            print(
                f"Task: [{task.metadata.get('Id', '')}] {task.metadata.get('Ti', '')}"
            )
            print(f"State: {state} (worktree/branch no longer exists)")

            if dry_run:
                print("Dry-run: Task would be archived.")
            elif input("Archive this task? [y/N]: ").strip().lower() == "y":
                self._move_logic(
                    os.path.basename(filepath), "ARCHIVED", force=True, yes=False
                )
        else:
            self._move_logic(
                os.path.basename(filepath), "ARCHIVED", force=True, yes=True
            )
            self.finish({"archived": True})

    def cleanup(self, dry_run=False, yes=False):
        from .commands import cleanup as cleanup_cmd

        cleanup_cmd.run(self, dry_run=dry_run, yes=yes)

    def config(self, action=None, key=None, value=None, save=False):
        from .commands import config as config_cmd

        config_cmd.run(self, action=action, key=key, value=value, save=save)

    def doctor(self, fix=False):
        from .commands import doctor as doctor_cmd

        doctor_cmd.run(self, fix=fix)

    def verify(self, task_id, proof):
        from .commands import verify as verify_cmd

        verify_cmd.run(self, task_id, proof)

    def audit(self, task_id):
        from .commands import audit as audit_cmd

        audit_cmd.run(self, task_id)

    def undo(self, filename):
        """Undo the last operation on a task by restoring previous state from git."""
        filepath, _current_state = self.find_task(filename)
        if not filepath:
            self.error(f"Task '{filename}' not found.")

        filepath_str = cast(str, filepath)
        fname = os.path.basename(filepath_str)
        # Scoping and matching must be exact: a substring match lets commits
        # about 11-task-x be mistaken for 1-task-x, and a global scan walks
        # every commit every agent ever wrote to the store.
        specs = [f":(glob)**/{fname}", f":(glob)**/{fname}/**"]
        with store_lock(self):
            scoped_commits = [
                c
                for c in self._run_git(
                    ["log", "--all", "--format=%h", "--", *specs], cwd=self.tasks_path
                )
                .stdout.strip()
                .split("\n")
                if c
            ]
            if not scoped_commits:
                self.error("Nothing to undo: no git history found.")
            if len(scoped_commits) < 2:
                self.error("Nothing to undo: first commit.")
            prev_commit = scoped_commits[0]
            prev_prev_commit = scoped_commits[1]

            if (
                self._run_git(
                    ["log", "-1", "--format=%s", prev_commit], cwd=self.tasks_path
                )
                .stdout.strip()
                .startswith("Undo:")
            ):
                self.error("Cannot undo twice.")

            tree_res = self._run_git(
                ["ls-tree", "--name-only", "-r", prev_prev_commit], cwd=self.tasks_path
            )
            # Slashes delimit path components, so '/<folder>/' cannot match
            # inside a longer sibling folder name.
            files_to_restore = [
                f for f in tree_res.stdout.strip().split("\n") if f"/{fname}/" in f
            ]

            # Never create temp files inside the shared store: any unscoped add
            # or another agent's checkpoint would sweep them into a commit.
            temp_dir = tempfile.mkdtemp(prefix="hammer_undo_")
            try:
                for file_path in files_to_restore:
                    out_path = os.path.join(temp_dir, os.path.basename(file_path))
                    content = self._run_git(
                        ["show", f"{prev_prev_commit}:{file_path}"], cwd=self.tasks_path
                    ).stdout
                    with open(out_path, "w") as f:
                        f.write(content)

                restored_task = FM.load(temp_dir)
                prev_state = restored_task.metadata.get("St", "BACKLOG")
                target_dir = os.path.join(
                    self.tasks_path, STATE_FOLDERS.get(prev_state, "backlog"), fname
                )

                if os.path.isdir(filepath_str):
                    shutil.rmtree(filepath_str)
                shutil.move(temp_dir, target_dir)
                commit_task_paths(
                    self,
                    target_dir,
                    f"Undo: restore {fname} to {prev_prev_commit[:7]}",
                    filepath_str,
                )
                self._append_log(target_dir, "Und")
                self.log(f"Undone: restored to {prev_state}")
                self.finish({"success": True, "previous_state": prev_state})
            except Exception:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                raise

    def upgrade(self):
        import subprocess

        if self.dev:
            # install.sh writes the real installation; dev mode must not touch it.
            self.error(
                "DEV_WRITE_BLOCKED",
                detail="'tasks upgrade' installs into the live installation",
                command="upgrade",
            )
        self.log("Upgrading tasks...")
        subprocess.run(["bash", str(Path(self.repo_script).parent / "install.sh")])  # noqa: PLW1510

    # --- Internals ---
    def _calculate_file_hash(self, filepath):
        """Calculate MD5 hash of a file"""
        try:
            hash_md5 = hashlib.md5()
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:  # noqa: BLE001
            return None

    def _write_counter_hash(self, counter_file, hash_file):
        """Write hash of counter file to hash file using atomic write"""
        try:
            file_hash = self._calculate_file_hash(counter_file)
            if file_hash:
                self._atomic_write(hash_file, file_hash)
        except Exception:  # noqa: BLE001, S110
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
        except Exception:  # noqa: BLE001
            return False

    def _recover_task_counter_from_tasks(self):
        """Recover task counter by scanning existing task IDs"""
        try:
            max_id = 0
            # Scan all state folders for existing tasks
            for folder in STATE_FOLDERS.values():
                state_path = os.path.join(self.tasks_path, folder)
                if not os.path.exists(state_path):
                    continue
                for item in os.listdir(state_path):
                    if item in [
                        ".gitkeep",
                        ".task_counter",
                        "task_counter",
                        ".task_counter.counter_hash",
                        ".task_counter.counter_backup",
                        ".task_counter.counter_backup.hash",
                    ]:
                        continue
                    item_path = os.path.join(state_path, item)
                    if not os.path.isdir(item_path):
                        continue
                    # Try to get ID from directory name (format: {id}-{type}-{title})
                    if "-" in item:
                        parts = item.split("-", 1)
                        if parts[0].isdigit():
                            task_id = int(parts[0])
                            max_id = max(max_id, task_id)
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
                                max_id = max(max_id, task_id)
                        except Exception:  # noqa: BLE001, S110
                            pass
            # Also check remote branches for higher IDs
            try:
                # Get remote branch names that might contain task IDs
                result = self._run_git(
                    ["ls-remote", "--heads", "origin"], cwd=self.root
                )
                if result.returncode == 0:
                    for line in result.stdout.strip().split("\n"):
                        if not line:
                            continue
                        parts = line.split("\t")
                        if len(parts) >= 2:
                            ref = parts[1]
                            # Look for refs like refs/heads/123-task-name
                            if ref.startswith("refs/heads/"):
                                branch_name = ref[11:]  # Remove refs/heads/
                                if "-" in branch_name:
                                    branch_parts = branch_name.split("-", 1)
                                    if branch_parts[0].isdigit():
                                        branch_id = int(branch_parts[0])
                                        max_id = max(max_id, branch_id)
            except Exception:  # noqa: BLE001, S110
                pass  # Fail silently for remote check

            return max_id
        except Exception:  # noqa: BLE001
            return 0

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
        return bool(os.path.isdir(logs_path) and os.listdir(logs_path))

    def _move_logic(self, filename, new_status, force=False, yes=False, sync=True):
        from .commands import move as move_cmd

        move_logic = move_cmd.move_logic
        move_logic(self, filename, new_status, force=force, yes=yes, sync=sync)
