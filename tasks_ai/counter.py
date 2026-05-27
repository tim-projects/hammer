import os
import hashlib

class TaskCounterProtector:
    """Protects and manages the task counter with hash verification and recovery."""
    def __init__(self, tasks_path, logger=None):
        self.tasks_path = tasks_path
        self.logger = logger
        self.counter_file = os.path.join(tasks_path, ".task_counter")
        self.hash_file = os.path.join(tasks_path, ".task_counter.hash")

    def get_next_id(self, cli):
        if not os.path.exists(self.counter_file):
            if os.path.exists(self.tasks_path):
                recovered_id = cli._recover_task_counter_from_tasks()
                current = recovered_id if recovered_id is not None else 0
            else:
                cli.error("Tasks not initialized. Run 'hammer tasks init' first.")
        else:
            if os.path.exists(self.hash_file):
                if not cli._verify_counter_hash(self.counter_file, self.hash_file):
                    if self.logger:
                        self.logger.log("Warning: Task counter hash mismatch. Attempting recovery.")
                    recovered_id = cli._recover_task_counter_from_tasks()
                    try:
                        with open(self.counter_file, "r") as f:
                            file_id = int(f.read().strip())
                    except Exception:
                        file_id = 0
                    current = max(file_id, recovered_id or 0)
                else:
                    with open(self.counter_file, "r") as f:
                        current = int(f.read().strip())
            else:
                with open(self.counter_file, "r") as f:
                    current = int(f.read().strip())

        current += 1
        cli._atomic_write(self.counter_file, str(current))
        cli._write_counter_hash(self.counter_file, self.hash_file)
        
        cli._run_git(["add", ".task_counter", ".task_counter.hash"], cwd=self.tasks_path)
        cli._run_git(
            ["commit", "--allow-empty", "-m", f"Bump task counter to {current}"],
            cwd=self.tasks_path,
        )
        return current
