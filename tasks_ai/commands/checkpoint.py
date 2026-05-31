import os
from ..utils import sync_task_content


def run(cli, filename=None):
    """Execution logic for 'tasks checkpoint'."""
    filepath, task = cli.get_active_task(filename)
    if not filepath or not task:
        cli.error("NO_ACTIVE_TASK")

    filepath_str = str(filepath)
    fname = os.path.basename(filepath_str)

    cli.log(f"Checkpointing {fname}...")
    if sync_task_content(cli, filepath_str, task):
        cli._atomic_write(filepath_str, task)
        cli._run_git(["add", "--all"], cwd=cli.tasks_path)
        cli._run_git(
            ["commit", "--allow-empty", "-m", f"Cp: {fname}"], cwd=cli.tasks_path
        )
        cli._append_log(filepath_str, "Cp")
        cli.log("Done.")
    else:
        cli._append_log(filepath_str, "Cp")
        cli.log("No changes.")

    cli.finish(
        {
            "id": task.metadata.get("Id"),
            "task_id": fname,
            "title": task.metadata.get("Ti", ""),
        }
    )
