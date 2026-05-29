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
