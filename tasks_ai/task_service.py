import os
from .file_manager import FM
from .constants import STATE_FOLDERS


class TaskService:
    def __init__(self, cli):
        self.cli = cli

    def find_task(self, name):
        """Find a task by its ID or filename."""
        if name is None:
            return None, None
        name = str(name)
        if not name or not self.cli._validate_task_id(name):
            return None, None

        task_id = name.rsplit(".", 1)[0]

        matches = []

        for state, folder in STATE_FOLDERS.items():
            state_dir = os.path.join(self.cli.tasks_path, folder)
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
                fp = os.path.join(self.cli.tasks_path, folder)
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

        if selected and self.cli._validate_path(selected[0]):
            # Integrity check: folder location must match metadata state
            task_path, state = selected
            folder_name = os.path.basename(os.path.dirname(task_path))
            if folder_name != STATE_FOLDERS.get(state):
                self.cli.error("INTEGRITY_VIOLATION")
            return selected
        return None, None

    def get_active_task(self, filename=None):
        """Find the task currently in PROGRESSING or a specific task if filename provided."""
        if filename:
            filepath, _ = self.find_task(filename)
            if filepath:
                return filepath, FM.load(filepath)
            return None, None

        prog_dir = os.path.join(self.cli.tasks_path, STATE_FOLDERS["PROGRESSING"])
        if not os.path.exists(prog_dir):
            return None, None

        items = [i for i in os.listdir(prog_dir) if i != ".gitkeep"]
        if not items:
            return None, None

        # If multiple, return the first one (usually should only be one)
        path = os.path.join(prog_dir, items[0])
        return path, FM.load(path)
