import os
from ..audit import generate_audit


def run(cli, task_id):
    # Find the task directory first to get its full folder name
    task_path, state = cli.find_task(task_id)
    if not task_path or state != "REVIEW":
        cli.error(f"Task {task_id} must be in REVIEW state to perform audit.",
                  hint="Move task to REVIEW: ./hammer tasks move <id> REVIEW")

    # Get the *actual* current filepath, which holds the folder name
    current_path, _ = cli.find_task(task_id)
    task_folder_name = os.path.basename(current_path)
    
    review_dir = os.path.join(cli.tasks_path, "review")
    patches_dir = os.path.join(review_dir, task_folder_name, "patches")

    if not os.path.exists(patches_dir) or not os.listdir(patches_dir):
        cli.error("AUDIT_PATCH_MISSING", patches_dir=patches_dir)

    output_path = os.path.join(review_dir, f"{task_folder_name}.audit")
    generate_audit(task_id, current_path, patches_dir, output_path)
    cli.log(f"✅ Audit log created for task {task_id}")
