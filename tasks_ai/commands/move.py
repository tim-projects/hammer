import os
import shutil
from datetime import datetime
from ..cli_errors import PipelineMergeConflict
from ..constants import STATE_FOLDERS
from ..file_manager import FM
from ..pipeline import PipelineError
from ..utils import parse_filename, perform_move

def run(cli, filename, new_status=None, yes=False):
    """Execution logic for 'tasks move'."""
    filepath, current_state = cli.find_task(filename)
    if not filepath:
        cli.error('TASK_NOT_FOUND', filename=filename)
    task = FM.load(filepath)
    if not new_status:
        new_status = cli.git.get_next_logical_state(current_state)
        if not new_status:
            cli.log(f'Task {filename} is already in terminal state {current_state}.')
            return
        if current_state == 'DONE' and new_status == 'ARCHIVED':
            done_at = task.metadata.get('DoneAt')
            if done_at:
                elapsed = datetime.now().timestamp() - done_at
                grace_period = 7 * 24 * 60 * 60
                if elapsed < grace_period:
                    days_left = round((grace_period - elapsed) / (24 * 3600), 1)
                    cli.log(f'Task {filename} is DONE. Auto-archiving in {days_left} days.')
                    return
            else:
                task.metadata['DoneAt'] = datetime.now().timestamp()
                cli._atomic_write(filepath, task)
                cli.log(f'Task {filename} marked as DONE today. Auto-archiving in 7 days.')
                return
    if isinstance(new_status, str) and ',' in new_status:
        states = [s.strip().upper() for s in new_status.split(',') if s.strip()]
        for state in states:
            try:
                success = move_logic(cli, filename, state, yes=yes)
            except Exception as e:
                cli.error(str(e))
            if not success:
                return
        _, final_state = cli.find_task(filename)
        fname = os.path.basename(filepath)
        task_id_num = task.metadata.get('Id', '')
        title = task.metadata.get('Ti', '')
        tt, _ = parse_filename(fname)
        cli.log(f'Moved: [{task_id_num}] {tt} | {title} -> {final_state}')
        cli.finish({'id': task_id_num, 'status': final_state})
        return
    try:
        success = move_logic(cli, filename, new_status, yes=yes)
    except Exception as e:
        cli.error(str(e))
    if success:
        fname = os.path.basename(filepath)
        task_id_num = task.metadata.get('Id', '')
        title = task.metadata.get('Ti', '')
        tt, _ = parse_filename(fname)
        cli.log(f'Moved: [{task_id_num}] {tt} | {title} -> {new_status}')
        cli.finish({'id': task_id_num, 'status': new_status})

def move_logic(cli, filename, new_status, force=False, yes=False, sync=True):
    """Internal move logic with pipeline gate enforcement."""
    new_status = new_status.upper()
    filepath, current_state = cli.find_task(filename)
    if not filepath:
        cli.error('TASK_NOT_FOUND', filename=filename)
    if current_state == new_status:
        cli.log(f'You are already on {new_status}')
        return False
    filepath_str = str(filepath)
    task = FM.load(filepath_str)
    task_type, _ = parse_filename(os.path.basename(filepath_str))
    allowed_transitions = cli.pipeline.get_allowed_transitions(task_type)
    if not force:
        try:
            cli._validate_pipeline_gate(task, new_status, filepath_str)
        except PipelineError as e:
            if e.code in ['AUDIT_MISSING', 'AUDIT_PATCH_MISSING', 'PROOF_MISSING', 'HASH_MISSING', 'AUDIT_MISMATCH', 'INTEGRITY_MISMATCH']:
                cli.log(f'Audit failed: {e.code}. Moving task back to PROGRESSING.')
                perform_move(cli, task, current_state, 'PROGRESSING', filepath_str)
                cli.error('AUDIT_FAILURE', hint_code='AUDIT_FAILURE', audit_code=e.code, task_id=str(task.metadata.get('Id', 'unknown')))
            else:
                raise
    cli.hook_registry.run_exit_hooks(cli, task, current_state, new_status, filepath_str, force=force)
    if not force:
        if new_status not in allowed_transitions.get(current_state, []):
            cli.error('FORBIDDEN_TRANSITION', from_state=current_state, to_state=new_status, task_id=os.path.basename(filepath_str).split('-')[0], next_valid_state='PROGRESSING')
        if new_status == 'ARCHIVED':
            _, branch = parse_filename(os.path.basename(filepath_str))
            if not cli.git.is_merged(branch, 'main'):
                cli.error('BRANCH_NOT_MERGED', branch=branch)
    if sync and (not force):
        try:
            cli._git_merge_transition(task, new_status, yes=yes)
        except PipelineMergeConflict as e:
            task_id = str(task.metadata.get('Id', 'unknown'))
            cli.error('MERGE_CONFLICT', branch=e.branch, default=e.default, task_id=task_id)
            return False
    staging_path = os.path.join(cli.tasks_path, '.ops', 'staging')
    os.makedirs(staging_path, exist_ok=True)
    staged_task_path = os.path.join(staging_path, os.path.basename(filepath_str))
    try:
        shutil.copytree(filepath_str, staged_task_path)
        new_task = FM.load(staged_task_path)
        new_filepath = os.path.join(cli.tasks_path, STATE_FOLDERS[new_status], os.path.basename(filepath_str))
        cli.hook_registry.run_enter_hooks(cli, new_task, current_state, new_status, staged_task_path)
        os.makedirs(os.path.dirname(new_filepath), exist_ok=True)
        if os.path.exists(new_filepath):
            for item in os.listdir(staged_task_path):
                src = os.path.join(staged_task_path, item)
                dst = os.path.join(new_filepath, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)
            shutil.rmtree(staged_task_path)
        else:
            os.rename(staged_task_path, new_filepath)
        if os.path.exists(filepath_str):
            if os.path.isdir(filepath_str):
                shutil.rmtree(filepath_str)
            else:
                os.remove(filepath_str)
    except Exception:
        if os.path.exists(staged_task_path):
            shutil.rmtree(staged_task_path)
        raise
    return True