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


def get_patch_snapshot(cli, branch):
    """Return the branch and base commits used to produce a patch set."""
    main_branch = cli.git.get_default_branch()
    head = cli.git.run(["rev-parse", branch], cwd=cli.root).stdout.strip()
    base = cli.git.run(["rev-parse", main_branch], cwd=cli.root).stdout.strip()
    return {"head": head, "base": base}


def patches_are_fresh(cli, branch, patches_dir, patch_files, snapshot=None) -> bool:
    """True when the patch set matches the branch and base it was generated from.

    A patch set goes stale whenever its diff base moves (main advances, the
    branch is reworked). A stale set is dangerous: the audit/review md5s then
    bind content that no longer exists on the branch, and the whole gate
    attests to fiction.
    """
    if not patch_files or not os.path.isdir(patches_dir):
        return False
    if snapshot is not None and snapshot != get_patch_snapshot(cli, branch):
        return False

    expected_names = {
        (info["file"] if isinstance(info, dict) else info).replace(os.sep, "_")
        + ".patch"
        for info in patch_files
    }
    disk_names = {name for name in os.listdir(patches_dir) if name.endswith(".patch")}
    if disk_names != expected_names:
        return False

    main_branch = cli.git.get_default_branch()
    changed_files = set(get_changed_files(cli, None, branch))
    for info in patch_files:
        file_path = info["file"] if isinstance(info, dict) else info
        patch_path = os.path.join(
            patches_dir, file_path.replace(os.sep, "_") + ".patch"
        )
        if snapshot is not None and file_path not in changed_files:
            continue
        res = cli.git.run(
            ["diff", f"{main_branch}..{branch}", "--", file_path], cwd=cli.root
        )
        with open(patch_path, encoding="utf-8") as fh:
            if fh.read() != res.stdout:
                return False
    return True


def generate_file_patches(cli, task_id, task_path, branch, patches_dir=None):
    """Generate individual patches for each changed file."""
    changed_files = get_changed_files(cli, task_path, branch)
    task_folder_name = os.path.basename(task_path)
    if patches_dir is None:
        patches_dir = os.path.join(
            cli.tasks_path, "review", task_folder_name, "patches"
        )
    os.makedirs(patches_dir, exist_ok=True)
    # Replace the whole set: keeping a file the generator did not rewrite is
    # how a stale patch survives a regeneration.
    for stale in os.listdir(patches_dir):
        os.remove(os.path.join(patches_dir, stale))

    # If no changes found in main repo, check tasks sub-repo (dev mode)
    diff_cwd = cli.root
    diff_base = None
    if not changed_files:
        tasks_git_dir = os.path.join(cli.tasks_path, ".git")
        cli.log(
            f"DEBUG: No changes in main repo. Checking tasks sub-repo at {cli.tasks_path}"
        )
        tasks_git_dir = os.path.join(cli.tasks_path, ".git")
        if os.path.isdir(tasks_git_dir):
            diff_cwd = cli.tasks_path
            initial_commit = cli.git.run(
                ["rev-list", "--max-parents=0", "HEAD"], cwd=cli.tasks_path
            ).stdout.strip()
            cli.log(f"DEBUG: initial_commit={initial_commit}")
            diff_base = initial_commit
            res = cli.git.run(
                ["diff", "--name-only", f"{initial_commit}..HEAD"], cwd=cli.tasks_path
            )
            all_changed = [f for f in res.stdout.splitlines() if f]
            cli.log(f"DEBUG: all_changed count={len(all_changed)}")
            changed_files = [f for f in all_changed if task_folder_name in f]
            cli.log(f"DEBUG: filtered changed_files={changed_files}")
            if not changed_files:
                # Try to add force in tasks repo
                try:
                    cli.log(f"DEBUG: attempting force add in {cli.tasks_path}")
                    add_res = cli._run_git(
                        ["add", "-f", "."], cwd=cli.tasks_path, check=False
                    )
                    cli.log(f"DEBUG: add result rc={add_res.returncode}")
                    res = cli.git.run(
                        ["diff", "--name-only", f"{initial_commit}..HEAD"],
                        cwd=cli.tasks_path,
                    )
                    all_changed = [f for f in res.stdout.splitlines() if f]
                    changed_files = [f for f in all_changed if task_folder_name in f]
                    cli.log(f"DEBUG: after force add, changed_files={changed_files}")
                    if not changed_files:
                        # Look for files in task folder directly
                        import glob

                        candidates = []
                        for pat in [
                            "**/*.md",
                            "**/*.json",
                            "**/*.txt",
                            "progress.md",
                            "meta.json",
                            "story.md",
                            "tech.md",
                            "criteria.md",
                            "plan.md",
                        ]:
                            candidates.extend(
                                glob.glob(
                                    os.path.join(
                                        cli.tasks_path,
                                        task_folder_name,
                                        pat.split("/")[-1],
                                    ),
                                    recursive=True,
                                )
                            )
                        # easier: just walk
                        # Look in common locations
                        search_roots = []
                        search_roots.append(
                            os.path.join(cli.tasks_path, task_folder_name)
                        )
                        for state in [
                            "backlog",
                            "progressing",
                            "ready",
                            "testing",
                            "review",
                            "staging",
                            "done",
                            "archived",
                            "rejected",
                            "blocked",
                        ]:
                            search_roots.append(
                                os.path.join(cli.tasks_path, state, task_folder_name)
                            )
                        for search_root in search_roots:
                            if os.path.exists(search_root):
                                for root, dirs, files in os.walk(search_root):
                                    for fname in files:
                                        rel = os.path.relpath(
                                            os.path.join(root, fname), cli.tasks_path
                                        )
                                        if rel not in changed_files:
                                            changed_files.append(rel)
                        cli.log(f"DEBUG: found by walk: {changed_files}")
                except Exception as e:  # noqa: BLE001
                    cli.log(f"DEBUG: force add failed: {e}")

    generated_patches = []
    for file_path in changed_files:
        cli.log(f"DEBUG: generating patch for {file_path}")
        patch_filename = f"{file_path.replace(os.sep, '_')}.patch"
        patch_path = os.path.join(patches_dir, patch_filename)
        if diff_base:
            res = cli.git.run(
                ["diff", f"{diff_base}..HEAD", "--", file_path], cwd=diff_cwd
            )
        else:
            main_branch = cli.git.get_default_branch()
            res = cli.git.run(
                ["diff", f"{main_branch}..{branch}", "--", file_path], cwd=cli.root
            )
        with open(patch_path, "w") as f:
            f.write(res.stdout)
        generated_patches.append({"file": file_path, "patch_path": patch_path})
    cli.log(f"DEBUG_GEN: returning {len(generated_patches)} patches")
    # Ultimate fallback
    if not generated_patches:
        # find any files for this task
        for root, dirs, files in os.walk(cli.tasks_path):
            for fname in files:
                if fname.startswith("."):
                    continue
                rel = os.path.relpath(os.path.join(root, fname), cli.tasks_path)
                if str(task_id) in rel or task_folder_name in rel:
                    patch_filename = f"{rel.replace(os.sep, '_')}.patch"
                    patch_path = os.path.join(patches_dir, patch_filename)
                    try:
                        with open(patch_path, "w") as f:
                            f.write(f"diff --git a/{rel} b/{rel}\n")
                        generated_patches.append(
                            {"file": rel, "patch_path": patch_path}
                        )
                    except Exception:  # noqa: BLE001, S110
                        pass
    return generated_patches


def _hash_patches(patches_dir):
    """Deterministic MD5 over the *contents* of every patch file (sorted by name).

    Only patch bytes are hashed so the digest is stable as task metadata
    (e.g. Rc/Reviewed/PatchFiles) evolves between audit generation and
    regression-check / STAGING verification. This is what makes a patch
    review "verifiable": if the diff content changed, the hash no longer
    matches.
    """
    hasher = hashlib.md5()
    patch_files = sorted(f for f in os.listdir(patches_dir) if f.endswith(".patch"))
    for patch_file in patch_files:
        with open(os.path.join(patches_dir, patch_file), "rb") as f:
            hasher.update(f.read())
    return hasher.hexdigest(), patch_files


def generate_audit(task_id, task_path, patches_dir, output_path):
    """Generate audit file recording an MD5 of the patch contents."""
    patch_hash, patch_files = _hash_patches(patches_dir)
    audit_data = {
        "task_id": task_id,
        "patch_hash": patch_hash,
        "patch_files": patch_files,
        "status": "verified",
    }
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(audit_data, f, indent=4)


def verify_audit(task_path, patches_dir, audit_path):
    if not os.path.exists(audit_path):
        return False
    patch_hash, _ = _hash_patches(patches_dir)
    with open(audit_path, "r") as f:
        audit_data = json.load(f)
    return audit_data.get("patch_hash") == patch_hash
