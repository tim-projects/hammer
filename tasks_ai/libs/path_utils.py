import os

def get_task_path(cli, folder, task_id):
    """Safely resolve task path based on CLI context."""
    return os.path.join(cli.tasks_path, folder, task_id)
