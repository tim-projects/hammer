import json
import os
from datetime import datetime

from ..constants import STATE_FOLDERS


def run(cli, task_id):
    """Isolated unarchive logic: ARCHIVED -> PROGRESSING, mounting the task worktree."""
    archived_dir = os.path.join(cli.tasks_path, STATE_FOLDERS["ARCHIVED"])

    task_dir = None
    for folder in os.listdir(archived_dir):
        if folder.startswith(f"{task_id}-"):
            task_dir = os.path.join(archived_dir, folder)
            break

    if not task_dir:
        cli.error("TASK_NOT_FOUND", filename=str(task_id))
        return

    meta_path = os.path.join(task_dir, "meta.json")
    with open(meta_path, "r") as f:
        meta = json.load(f)
    branch = meta.get("Br")

    if not branch:
        cli.error(
            "TASK_METADATA_CORRUPTED", detail=f"Task {task_id} missing 'Br' metadata."
        )
        return

    # Mount worktree (creates or reuses)
    worktree_path = cli.git.worktrees.create_task_worktree(str(task_id), branch)
    if worktree_path:
        cli.console("worktree", "mount", f"{branch}")
    else:
        cli.log(
            f"Warning: Could not create worktree for branch {branch}, continuing anyway."
        )

    # 4. Move folder
    progressing_dir = os.path.join(cli.tasks_path, STATE_FOLDERS["PROGRESSING"])
    os.makedirs(progressing_dir, exist_ok=True)
    new_dir = os.path.join(progressing_dir, os.path.basename(task_dir))
    os.rename(task_dir, new_dir)

    # 5. Log & Metadata
    meta["St"] = "PROGRESSING"
    with open(os.path.join(new_dir, "meta.json"), "w") as f:
        json.dump(meta, f, indent=2)

    log_path = os.path.join(new_dir, "activity.log")
    with open(log_path, "a") as f:
        f.write(
            f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ARCHIVED->PROGRESSING (UNARCHIVE)\n"  # noqa: DTZ005
        )

    print(
        f"Task {task_id} successfully unarchived to PROGRESSING. Worktree: {worktree_path}"
    )
