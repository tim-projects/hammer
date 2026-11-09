import os

from ..file_manager import FM
from ..utils import commit_task_paths, parse_filename


def run(cli, filename, blocked_by_filename):
    """Execution logic for 'tasks unlink'."""
    f1, _ = cli.find_task(filename)
    f2, _ = cli.find_task(blocked_by_filename)
    if not f1 or not f2:
        cli.error("LINK_TASK_NOT_FOUND")
    f1_str, f2_str = (str(f1), str(f2))
    if os.path.abspath(f1_str) == os.path.abspath(f2_str):
        cli.error("LINK_SELF")
    f1_fname = os.path.basename(f1_str)
    f2_fname = os.path.basename(f2_str)
    b_name = f2_fname
    task = FM.load(f1_str)
    task_title = str(task.metadata.get("Ti", ""))
    task_id_num = str(task.metadata.get("Id", ""))
    tt, _ = parse_filename(f1_fname)
    bl = task.metadata.get("Bl", [])
    if not isinstance(bl, list):
        bl = []
    b_task = FM.load(f2_str)
    b_title = str(b_task.metadata.get("Ti", ""))
    b_id = str(b_task.metadata.get("Id", ""))
    b_tt, _ = parse_filename(f2_fname)
    if b_name not in bl:
        cli.log(f"Not linked: [{task_id_num}] {tt} -> [{b_id}] {b_tt}")
        cli.finish(
            {
                "id": task_id_num,
                "task_id": filename,
                "unlinked_from": b_name,
                "changed": False,
            }
        )
    bl.remove(b_name)
    task.metadata["Bl"] = bl
    cli._atomic_write(f1_str, task)
    cli._append_log(f1_str, "Unlk")
    # Only this task's record: a store-wide add would commit every other
    # agent's pending work under this unlink's message.
    commit_task_paths(cli, f1_str, f"Unlk {filename}->{b_name}")
    cli.log(
        f"Unlinked: [{task_id_num}] {tt} | {task_title} -> [{b_id}] {b_tt} | {b_title}"
    )
    cli.finish(
        {
            "id": task_id_num,
            "task_id": filename,
            "unlinked_from": b_name,
            "unlinked_from_title": b_title,
        }
    )
