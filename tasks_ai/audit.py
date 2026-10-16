import hashlib
import json
import os

def get_changed_files(cli, task_path, branch):
    """Get list of files changed in the task branch compared to main."""
    main_branch = cli.git.get_default_branch()
    res = cli.git.run(['diff', '--name-only', f'{main_branch}...{branch}'], cwd=cli.root)
    return [f for f in res.stdout.splitlines() if f]

def generate_file_patches(cli, task_id, task_path, branch):
    """Generate individual patches for each changed file."""
    changed_files = get_changed_files(cli, task_path, branch)
    task_folder_name = os.path.basename(task_path)
    patches_dir = os.path.join(cli.tasks_path, 'review', task_folder_name, 'patches')
    cli.log(f'DEBUG: patches_dir={patches_dir}, changed_files={changed_files}')
    os.makedirs(patches_dir, exist_ok=True)

    # If no changes found in main repo, check tasks sub-repo (dev mode)
    diff_cwd = cli.root
    diff_base = None
    if not changed_files:
        cli.log('DEBUG_FALLBACK_TRIGGERED')
        tasks_git_dir = os.path.join(cli.tasks_path, '.git')
        cli.log(f'DEBUG: No changes in main repo. Checking tasks sub-repo at {cli.tasks_path}')
        cli.log(f'DEBUG: tasks_git_dir={tasks_git_dir}, exists={os.path.isdir(tasks_git_dir)}')
        if os.path.isdir(tasks_git_dir):
            diff_cwd = cli.tasks_path
            initial_commit = cli.git.run(
                ['rev-list', '--max-parents=0', 'HEAD'],
                cwd=cli.tasks_path
            ).stdout.strip()
            cli.log(f'DEBUG: initial_commit={initial_commit}')
            diff_base = initial_commit
            res = cli.git.run(
                ['diff', '--name-only', f'{initial_commit}..HEAD'],
                cwd=cli.tasks_path
            )
            all_changed = [f for f in res.stdout.splitlines() if f]
            cli.log(f'DEBUG: all_changed count={len(all_changed)}')
            changed_files = [f for f in all_changed if task_folder_name in f]
            cli.log(f'DEBUG: filtered changed_files={changed_files}')
            if not changed_files:
                # Try to add force in tasks repo
                try:
                    cli._run_git(['add', '-f', '.'], cwd=cli.tasks_path)
                    res = cli.git.run(
                        ['diff', '--name-only', f'{initial_commit}..HEAD'],
                        cwd=cli.tasks_path
                    )
                    all_changed = [f for f in res.stdout.splitlines() if f]
                    changed_files = [f for f in all_changed if task_folder_name in f]
                    cli.log(f'DEBUG: after force add, changed_files={changed_files}')
                except Exception as e:
                    cli.log(f'DEBUG: force add failed: {e}')

    generated_patches = []
    for file_path in changed_files:
        cli.log(f'DEBUG: generating patch for {file_path}')
        patch_filename = f"{file_path.replace(os.sep, '_')}.patch"
        patch_path = os.path.join(patches_dir, patch_filename)
        if diff_base:
            res = cli.git.run(
                ['diff', f'{diff_base}..HEAD', '--', file_path],
                cwd=diff_cwd
            )
        else:
            main_branch = cli.git.get_default_branch()
            res = cli.git.run(['diff', f'{main_branch}..{branch}', '--', file_path], cwd=cli.root)
        with open(patch_path, 'w') as f:
            f.write(res.stdout)
        generated_patches.append({'file': file_path, 'patch_path': patch_path})
    cli.log(f"DEBUG_GEN: returning {len(generated_patches)} patches")
    return generated_patches

def generate_audit(task_id, task_path, patches_dir, output_path):
    """Generate audit file based on patches, meta.json, and criteria.md."""
    hasher = hashlib.md5()
    patch_files = sorted([f for f in os.listdir(patches_dir) if f.endswith('.patch')])
    for patch_file in patch_files:
        with open(os.path.join(patches_dir, patch_file), 'rb') as f:
            hasher.update(f.read())
    for filename in ['meta.json', 'criteria.md']:
        filepath = os.path.join(task_path, filename)
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                hasher.update(f.read())
    audit_data = {'task_id': task_id, 'patch_hash': hasher.hexdigest(), 'status': 'verified'}
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(audit_data, f, indent=4)
    print(f'Audit file generated at {output_path}')

def verify_audit(task_path, patches_dir, audit_path):
    if not os.path.exists(audit_path):
        return False
    hasher = hashlib.md5()
    patch_files = sorted([f for f in os.listdir(patches_dir) if f.endswith('.patch')])
    for patch_file in patch_files:
        with open(os.path.join(patches_dir, patch_file), 'rb') as f:
            hasher.update(f.read())
    for filename in ['meta.json', 'criteria.md']:
        filepath = os.path.join(task_path, filename)
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                hasher.update(f.read())
    with open(audit_path, 'r') as f:
        audit_data = json.load(f)
    return audit_data['patch_hash'] == hasher.hexdigest()