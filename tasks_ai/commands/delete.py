import os
import shutil
import secrets
from ..constants import STATE_FOLDERS
from ..file_manager import FM
from ..utils import parse_filename


def run(cli, filename, confirm=None):
    """Execution logic for 'tasks delete'."""
    filepath, current_state = cli.find_task(filename)
    if not filepath:
        cli.error("TASK_NOT_FOUND", filename=filename)

    if not cli._validate_path(filepath):
        cli.error("INVALID_TASK_PATH", filepath=filepath)

    filepath_str = str(filepath)
    task = FM.load(filepath_str)
    fname = os.path.basename(filepath_str)
    task_id = fname.rsplit(".", 1)[0]
    tt, _ = parse_filename(fname)

    # Move to REJECTED if no confirm code
    if not confirm:
        delete_code = secrets.token_hex(8)
        task.metadata["DeleteCode"] = delete_code
        cli._atomic_write(filepath_str, task)
        cli._move_logic(task_id, "REJECTED", force=True)

        new_filepath = os.path.join(cli.tasks_path, STATE_FOLDERS["REJECTED"], fname)
        cli._append_log(new_filepath, "Del")

        cli.finish(
            {
                "id": task.metadata.get("Id"),
                "task_id": task_id,
                "title": task.metadata.get("Ti", ""),
                "state": "REJECTED",
                "delete_code": delete_code,
            }
        )

    # Permanent deletion
    if current_state != "REJECTED":
        cli.error(
            f"Task must be in REJECTED state to delete. Currently in {current_state}.",
            hint="Use 'hammer tasks delete <id>' first to move to REJECTED, then confirm.",
        )

    try:
        cli._append_log(filepath_str, "Del")
        if os.path.isdir(filepath_str):
            shutil.rmtree(filepath_str)
        else:
            os.remove(filepath_str)

        cli._run_git(["add", "--all"], cwd=cli.tasks_path)
        cli._run_git(
            ["commit", "--allow-empty", "-m", f"Del {task_id}"], cwd=cli.tasks_path
        )

        cli.log(
            f"Deleted: [{task.metadata.get('Id', '')}] {tt} | {task.metadata.get('Ti', '')}"
        )
    except Exception as e:
        cli.error(str(e))

    cli.finish(
        {
            "id": task.metadata.get("Id"),
            "task_id": task_id,
            "title": task.metadata.get("Ti", ""),
            "state": "DELETED",
        }
    )
