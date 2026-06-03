import os
import json
from datetime import datetime
from ..constants import STATE_FOLDERS


def run(cli, task_id):
    """Isolated unarchive logic: ARCHIVED -> PROGRESSING"""
    archived_dir = os.path.join(cli.tasks_path, STATE_FOLDERS["ARCHIVED"])

    # 1. Find the task
    task_dir = None
    for folder in os.listdir(archived_dir):
        if folder.startswith(f"{task_id}-"):
            task_dir = os.path.join(archived_dir, folder)
            break

    if not task_dir:
        cli.error("TASK_NOT_FOUND", filename=str(task_id))
        return

    # 2. Get branch
    meta_path = os.path.join(task_dir, "meta.json")
    with open(meta_path, "r") as f:
        meta = json.load(f)
    branch = meta.get("Br")

    if not branch:
        cli.error(
            "TASK_METADATA_CORRUPTED", detail=f"Task {task_id} missing 'Br' metadata."
        )
        return

    # 3. Handle branch
    # Check if local
    local_branches = cli._run_git(
        ["branch", "--format", "%(refname:short)"]
    ).stdout.splitlines()
    if branch not in local_branches:
        # Check remote
        if cli._run_git(["ls-remote", "--heads", "origin", branch]).stdout:
            cli._run_git(["fetch", "origin", branch])
            cli._run_git(["checkout", "-b", branch, f"origin/{branch}"])
        else:
            cli.error("BRANCH_NOT_FOUND", branch=branch)
            return
    else:
        cli._run_git(["checkout", branch])

    # 4. Move folder
    progressing_dir = os.path.join(cli.tasks_path, STATE_FOLDERS["PROGRESSING"])
    os.makedirs(progressing_dir, exist_ok=True)
    new_dir = os.path.join(progressing_dir, os.path.basename(task_dir))
    os.rename(task_dir, new_dir)

    # 5. Log & Metadata
    meta["state"] = "PROGRESSING"
    with open(os.path.join(new_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    log_path = os.path.join(new_dir, "activity.log")
    with open(log_path, "a") as f:
        f.write(
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ARCHIVED->PROGRESSING (UNARCHIVE)\n"
        )

    print(f"Task {task_id} successfully unarchived to PROGRESSING.")
