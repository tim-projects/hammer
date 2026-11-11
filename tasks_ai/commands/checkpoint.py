import os

from ..utils import commit_task_paths, sync_task_content


def run(cli, filename=None):
    """Execution logic for 'tasks checkpoint'."""
    filepath, task = cli.get_active_task(filename)
    if not filepath or not task:
        candidates = cli.processing_candidates()
        cli.error(
            "NO_ACTIVE_TASK",
            usage="./hammer tasks checkpoint <id>",
            candidates=", ".join(candidates) if candidates else "none",
        )
    filepath_str = str(filepath)
    fname = os.path.basename(filepath_str)
    cli.log(f"Checkpointing {fname}...")
    updated = sync_task_content(cli, filepath_str, task)
    if updated:
        cli._atomic_write(filepath_str, task)
    # The log line is written before the commit, otherwise it stays on disk
    # uncommitted until this task's next checkpoint.
    cli._append_log(filepath_str, "Cp")
    commit_task_paths(cli, filepath_str, f"Cp: {fname}")
    cli.log("Done." if updated else "No changes.")
    cli.finish(
        {
            "id": task.metadata.get("Id"),
            "task_id": fname,
            "title": task.metadata.get("Ti", ""),
        }
    )
