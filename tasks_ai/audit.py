import hashlib
import json
import os


def get_changed_files(cli, task_path, branch):
    """Get list of files changed in the task branch compared to main."""
    main_branch = cli.git.get_default_branch()
    res = cli.git.run(
        ["diff", "--name-only", f"{main_branch}...{branch}"], cwd=cli.root
    )
    return [f for f in res.stdout.splitlines() if f]


def generate_file_patches(cli, task_id, task_path, branch):
    """Generate individual patches for each changed file."""
    changed_files = get_changed_files(cli, task_path, branch)
    cli.log(f"DEBUG: branch={branch}, changed_files={changed_files}")

    task_folder_name = os.path.basename(task_path)
    patches_dir = os.path.join(cli.tasks_path, "review", task_folder_name, "patches")
    cli.log(f"DEBUG: patches_dir={patches_dir}")
    os.makedirs(patches_dir, exist_ok=True)

    generated_patches = []
    for file_path in changed_files:
        cli.log(f"DEBUG: generating patch for {file_path}")
        patch_filename = f"{file_path.replace(os.sep, '_')}.patch"
        patch_path = os.path.join(patches_dir, patch_filename)

        # Generate diff for this file
        main_branch = cli.git.get_default_branch()
        res = cli.git.run(
            ["diff", f"{main_branch}..{branch}", "--", file_path], cwd=cli.root
        )

        with open(patch_path, "w") as f:
            f.write(res.stdout)

        generated_patches.append({"file": file_path, "patch_path": patch_path})

    return generated_patches


def generate_audit(task_id, task_path, patches_dir, output_path):
    """Generate audit file based on all patches."""
    hasher = hashlib.md5()

    patch_files = sorted([f for f in os.listdir(patches_dir) if f.endswith(".patch")])
    for patch_file in patch_files:
        with open(os.path.join(patches_dir, patch_file), "rb") as f:
            hasher.update(f.read())

    audit_data = {
        "task_id": task_id,
        "patch_hash": hasher.hexdigest(),
        "status": "verified",
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(audit_data, f, indent=4)
    print(f"Audit file generated at {output_path}")


def verify_audit(patches_dir, audit_path):
    if not os.path.exists(audit_path):
        return False

    hasher = hashlib.md5()
    patch_files = sorted([f for f in os.listdir(patches_dir) if f.endswith(".patch")])
    for patch_file in patch_files:
        with open(os.path.join(patches_dir, patch_file), "rb") as f:
            hasher.update(f.read())

    with open(audit_path, "r") as f:
        audit_data = json.load(f)
    return audit_data["patch_hash"] == hasher.hexdigest()
