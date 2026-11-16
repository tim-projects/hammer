import os

from ..file_manager import FM
from ..pipeline_hooks import WorktreeSyncHook


def run(cli, task_id):
    """Execution logic for 'tasks mount <id>'."""
    filepath, _ = cli.find_task(task_id)
    if not filepath:
        cli.error("TASK_NOT_FOUND", filename=str(task_id))

    task = FM.load(str(filepath))
    branch = task.metadata.get("Br", "") or str(task_id)
    task_id = str(task.metadata.get("Id", task_id))

    hook = WorktreeSyncHook()
    wt_path = hook.ensure_worktree(cli, task_id, branch)
    if not wt_path:
        cli.error("WORKTREE_NOT_FOUND", task_id=task_id)

    # Path first: a synchronization blocker must never bury where to go.
    cli.log(f"Worktree mounted at: {wt_path}")
    cli.log(f"Run: cd {wt_path}")

    hook.synchronize(cli, task_id, branch, wt_path)

    cli.finish(
        {
            "id": task.metadata.get("Id"),
            "task_id": branch,
            "branch": branch,
            "worktree_path": wt_path,
            "cwd": os.getcwd(),
        }
    )
