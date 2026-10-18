import os

from ..audit import generate_audit
from ..file_manager import FM


def run(cli, task_id):
    task_path, state = cli.find_task(task_id)
    if not task_path or state != 'REVIEW':
        cli.error(f'Task {task_id} must be in REVIEW state to perform audit.', hint='Move task to REVIEW: ./hammer tasks move <id> REVIEW')
    current_path, _ = cli.find_task(task_id)
    task = FM.load(current_path)
    branch = task.metadata.get('Branch') or task.metadata.get('branch') or ''
    task_folder_name = os.path.basename(current_path)
    if task.metadata.get('Rc') == 'PASSED':
        cli.log(f'✅ No changes detected for task {task_id} (already merged or empty diff). Skipping audit.')
        return
    review_dir = os.path.join(cli.tasks_path, 'review')
    patches_dir = os.path.join(review_dir, task_folder_name, 'patches')
    if not os.path.exists(patches_dir) or not os.listdir(patches_dir):
        from ..audit import generate_file_patches
        try:
            patches = generate_file_patches(cli, str(task_id), current_path, branch)
            # Double-check - sometimes patches might not be written
            if not patches or not os.path.exists(patches_dir) or not os.listdir(patches_dir):
                # Try one more time
                patches = generate_file_patches(cli, str(task_id), current_path, branch)
            if not patches or not os.path.exists(patches_dir) or not os.listdir(patches_dir):
                cli.error('AUDIT_PATCH_MISSING', patches_dir=patches_dir)
            task.metadata["PatchFiles"] = patches
            FM.save(task, current_path)
        except Exception:
            cli.error('AUDIT_PATCH_MISSING', patches_dir=patches_dir)
    output_path = os.path.join(review_dir, f'{task_folder_name}.audit')
    generate_audit(task_id, current_path, patches_dir, output_path)
    cli.log(f'✅ Audit log created for task {task_id}')
