import os
from ..audit import generate_audit


def run(cli, task_id):
    # Find the patch file that starts with the task_id
    patch_dir = ".tasks/review"
    patch_file = None
    for f in os.listdir(patch_dir):
        if f.startswith(task_id) and f.endswith(".patch"):
            patch_file = os.path.join(patch_dir, f)
            break

    if not patch_file:
        cli.error(f"Patch file not found for task {task_id}")
        return

    output_path = patch_file.replace(".patch", ".audit")
    generate_audit(task_id, patch_file, output_path)
    cli.log(f"✅ Audit log created for task {task_id}")
