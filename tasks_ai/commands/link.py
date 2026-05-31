import os
from ..file_manager import FM
from ..utils import parse_filename, has_path


def run(cli, filename, blocked_by_filename):
    """Execution logic for 'tasks link'."""
    f1, _ = cli.find_task(filename)
    f2, _ = cli.find_task(blocked_by_filename)

    if not f1 or not f2:
        cli.error("LINK_TASK_NOT_FOUND")

    f1_str, f2_str = str(f1), str(f2)

    if os.path.abspath(f1_str) == os.path.abspath(f2_str):
        cli.error("LINK_SELF")

    f1_fname = os.path.basename(f1_str)
    f2_fname = os.path.basename(f2_str)

    task = FM.load(f1_str)
    task_title = str(task.metadata.get("Ti", ""))
    task_id_num = str(task.metadata.get("Id", ""))
    tt, _ = parse_filename(f1_fname)
    bl = task.metadata.get("Bl", [])
    if not isinstance(bl, list):
        bl = []

    b_name = f2_fname
    b_task = FM.load(f2_str)
    b_title = str(b_task.metadata.get("Ti", ""))
    b_id = str(b_task.metadata.get("Id", ""))
    b_tt, _ = parse_filename(f2_fname)

    # Check for circular dependency
    if has_path(b_id, task_id_num, cli.tasks_path, FM):
        cli.error(
            "CIRCULAR_DEPENDENCY",
            filename=filename,
            blocked_by=blocked_by_filename
        )

    if b_name not in bl:
        bl.append(b_name)
        task.metadata["Bl"] = bl
        cli._atomic_write(f1_str, task)
        cli._append_log(f1_str, "Lk")
        cli._run_git(["add", "--all"], cwd=cli.tasks_path)
        cli._run_git(
            ["commit", "--allow-empty", "-m", f"Lk {filename}->{b_name}"],
            cwd=cli.tasks_path,
        )
        cli.log(
            f"Linked: [{task_id_num}] {tt} | {task_title} -> [{b_id}] {b_tt} | {b_title}"
        )
    cli.finish(
        {
            "id": task_id_num,
            "task_id": filename,
            "title": task_title,
            "linked_to": b_name,
            "linked_to_title": b_title,
        }
    )
