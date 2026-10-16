import os

from ..audit import generate_audit
from ..file_manager import FM


def run(cli, task_id):
    task_path, state = cli.find_task(task_id)
    if not task_path or state != 'REVIEW':
        cli.error(f'Task {task_id} must be in REVIEW state to perform audit.', hint='Move task to REVIEW: ./hammer tasks move <id> REVIEW')
    current_path, _ = cli.find_task(task_id)
    task_folder_name = os.path.basename(current_path)
    task = FM.load(current_path)
    if task.metadata.get('Rc') == 'PASSED':
        cli.log(f'✅ No changes detected for task {task_id} (already merged or empty diff). Skipping audit.')
        return
    review_dir = os.path.join(cli.tasks_path, 'review')
    patches_dir = os.path.join(review_dir, task_folder_name, 'patches')
    cli.log(f'DEBUG_AUDIT_CMD: checking patches_dir={patches_dir}, exists={os.path.exists(patches_dir)}')
    if os.path.exists(patches_dir):
        cli.log(f'DEBUG_AUDIT_CMD: files={os.listdir(patches_dir)}')
    if not os.path.exists(patches_dir) or not os.listdir(patches_dir):
        cli.error('AUDIT_PATCH_MISSING', patches_dir=patches_dir)
    output_path = os.path.join(review_dir, f'{task_folder_name}.audit')
    generate_audit(task_id, current_path, patches_dir, output_path)
    cli.log(f'✅ Audit log created for task {task_id}')