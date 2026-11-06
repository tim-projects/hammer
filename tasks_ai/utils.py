import os
import shutil
import tempfile
from typing import Any

from tasks_ai.file_manager import FM


def parse_filename(name: str) -> tuple[str, str]:
    """Parse task filename to extract type and slug."""
    if not name:
        return ('task', '')
    name_part = str(name).rsplit('.', 1)[0]
    if '-' in name_part:
        parts = name_part.split('-', 2)
        if len(parts) >= 3:
            return (parts[1], name_part)
    if '_' in name_part:
        parts = name_part.split('_', 1)
        return (parts[0], parts[1])
    return ('task', name_part)

def atomic_write(path: str, task_or_content: Any, fm=None):
    """
    Write task or raw content to path atomically.
    Supports both single-file tasks (.md) and multi-file task directories.
    """
    if hasattr(task_or_content, 'metadata'):
        if path.endswith('.md'):
            if fm:
                fm.dump(task_or_content, path)
            else:
                from .file_manager import FM
                FM.dump(task_or_content, path)
        else:
            parent_dir = os.path.dirname(path.rstrip('/'))
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            temp_dir = tempfile.mkdtemp(dir=parent_dir or '.')
            try:
                if os.path.isdir(path):
                    for item in os.listdir(path):
                        src_item = os.path.join(path, item)
                        dst_item = os.path.join(temp_dir, item)
                        if os.path.isdir(src_item):
                            shutil.copytree(src_item, dst_item)
                        else:
                            shutil.copy2(src_item, dst_item)
                if fm:
                    fm.dump(task_or_content, temp_dir)
                else:
                    from .file_manager import FM
                    FM.dump(task_or_content, temp_dir)
                if os.path.exists(path):
                    if os.path.isdir(path):
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                os.rename(temp_dir, path)
            except Exception:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                raise

def store_is_git(cli):
    """True when the store lives inside a git work tree.

    'tasks init' clones the store's own repo, but a store can also be a plain
    directory that was never initialised; those have no history to write to, so
    store writes are skipped there instead of failing the command.
    """
    res = cli._run_git(['rev-parse', '--is-inside-work-tree'], cwd=cli.tasks_path)
    return res.returncode == 0 and res.stdout.strip() == 'true'

def commit_task_paths(cli, task_filepath, message, *moved_away_paths):
    """Stage and commit only these task paths in the shared store.

    The store is one git repo shared by every agent, so 'add --all' would commit
    other tasks' uncommitted records under our message. A failing add or commit
    must be fatal: a silent failure writes to disk but never to the record.
    Paths passed in moved_away_paths are recorded as deletions (a move leaves the
    old state folder behind).
    """
    if not store_is_git(cli):
        return
    paths = [os.path.relpath(p, cli.tasks_path)
             for p in (task_filepath, *moved_away_paths) if p]
    add = cli._run_git(['add', '--', *paths], cwd=cli.tasks_path)
    if add.returncode != 0:
        cli.error('STORE_WRITE_FAIL', message=message,
                  detail=(add.stderr or '').strip() or 'git add failed')
    commit = cli._run_git(['commit', '--allow-empty', '-m', message], cwd=cli.tasks_path)
    if commit.returncode != 0:
        cli.error('STORE_WRITE_FAIL', message=message,
                  detail=(commit.stderr or '').strip() or 'git commit failed')

def sync_task_content(cli, filepath, task, is_final=False) -> bool:
    """Sync task metadata with current branch commits, notes and store changes."""
    from .constants import CURRENT_TASK_FILENAME
    if not filepath:
        return False
    filepath_str = str(filepath)
    tn = os.path.basename(filepath_str)
    _, branch = parse_filename(tn)
    updated = False
    main_root = cli.context.main_repo_root
    default_branch = 'main'
    for b in ['main', 'master']:
        if cli._run_git(['rev-parse', '--verify', b], cwd=main_root).returncode == 0:
            default_branch = b
            break
    res = cli._run_git(['log', branch, f'^{default_branch}', '--oneline'], cwd=main_root)
    commits = res.stdout.strip() if res.returncode == 0 else ''
    if commits:
        task.parts['commits'] = commits
        updated = True
    dump_path = os.path.join(filepath_str, CURRENT_TASK_FILENAME)
    if os.path.exists(dump_path):
        dump = FM.load(dump_path)
        if dump.parts.get('content'):
            task.parts['notes'] = dump.parts['content']
            updated = True
    # The task record lives in the shared store, which the main repo ignores, so
    # pending changes are detected in the store repo and part files are read
    # straight off disk instead of diffed against the main repo.
    rel_task_dir = os.path.relpath(filepath_str, cli.tasks_path)
    if store_is_git(cli):
        res_status = cli._run_git(['status', '--porcelain', '--', rel_task_dir], cwd=cli.tasks_path)
        if res_status.returncode != 0:
            cli.error('STORE_WRITE_FAIL', message='inspect task record',
                      detail=(res_status.stderr or '').strip() or 'git status failed')
        if res_status.stdout.strip():
            updated = True
    if os.path.isdir(filepath_str):
        for entry in sorted(os.listdir(filepath_str)):
            if not entry.endswith('.md') or entry == CURRENT_TASK_FILENAME:
                continue
            try:
                with open(os.path.join(filepath_str, entry), 'r', encoding='utf-8') as f:
                    content = f.read()
            except OSError:
                continue
            part_name = entry[:-3]
            if task.parts.get(part_name) != content:
                task.parts[part_name] = content
                updated = True
    return updated

def perform_move(cli, task, current_state, new_status, filepath):
    """Execute the physical move of task files on disk, including auxiliary artifacts."""
    from .constants import STATE_FOLDERS
    from .file_manager import FM
    if not filepath:
        cli.error('Invalid task path.')
    filepath_str = str(filepath)
    sync_task_content(cli, filepath_str, task, is_final=new_status == 'ARCHIVED')
    task.metadata.pop('St', None)
    fname = task.metadata.get('Br') or str(task.metadata.get('Id', 'unknown-task'))
    new_filepath = os.path.join(cli.tasks_path, STATE_FOLDERS[new_status], fname)
    if filepath_str != new_filepath:
        atomic_write(new_filepath, task, fm=FM)
        task_folder_name = os.path.basename(filepath_str)
        patches_src = os.path.join(cli.tasks_path, 'review', task_folder_name, 'patches')
        patches_dst = os.path.join(cli.tasks_path, STATE_FOLDERS[new_status], fname, 'patches')
        if os.path.exists(patches_src):
            os.makedirs(os.path.dirname(patches_dst), exist_ok=True)
            shutil.move(patches_src, patches_dst)
            cli.log(f'Migrated patches directory to {new_status}')
        audit_src = os.path.join(cli.tasks_path, 'review', f'{task_folder_name}.audit')
        audit_dst = os.path.join(cli.tasks_path, STATE_FOLDERS[new_status], f'{fname}.audit')
        if os.path.exists(audit_src):
            shutil.move(audit_src, audit_dst)
            cli.log(f'Migrated audit file to {new_status}')
        if os.path.exists(filepath_str):
            if os.path.isdir(filepath_str):
                shutil.rmtree(filepath_str)
            else:
                os.remove(filepath_str)
    else:
        atomic_write(new_filepath, task, fm=FM)
    cli._append_log(new_filepath, f'{current_state}->{new_status}')
    return task

def has_path(start_id: str, target_id: str, tasks_path: str, fm, visited=None) -> bool:
    """Check if there's a path from start_id to target_id via BlockedBy links."""
    import json

    from .constants import STATE_FOLDERS
    if visited is None:
        visited = set()
    if start_id in visited:
        return False
    visited.add(start_id)
    task_file = None
    for state_folder in STATE_FOLDERS.values():
        state_path = os.path.join(tasks_path, state_folder)
        if not os.path.exists(state_path):
            continue
        for task_dir in os.listdir(state_path):
            task_dir_path = os.path.join(state_path, task_dir)
            if not os.path.isdir(task_dir_path):
                continue
            meta_file = os.path.join(task_dir_path, 'meta.json')
            if os.path.exists(meta_file):
                try:
                    with open(meta_file, 'r') as f:
                        meta = json.load(f)
                    if str(meta.get('Id')) == str(start_id):
                        task_file = task_dir_path
                        break
                except (OSError, json.JSONDecodeError):
                    pass
        if task_file:
            break
    if not task_file:
        return False
    try:
        task = fm.load(task_file)
        bl = task.metadata.get('Bl', [])
        if not isinstance(bl, list):
            bl = []
        for blocker_dir in bl:
            blocker_id = blocker_dir.split('-')[0] if '-' in blocker_dir else blocker_dir
            if str(blocker_id) == str(target_id):
                return True
            if has_path(blocker_id, target_id, tasks_path, fm, visited):
                return True
    except Exception:  # noqa: BLE001, S110
        pass
    return False