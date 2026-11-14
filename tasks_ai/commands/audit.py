import os

from ..audit import generate_audit
from ..file_manager import FM
from ..utils import commit_task_paths, parse_filename


def run(cli, task_id):
    task_path, state = cli.find_task(task_id)
    if not task_path or state != "REVIEW":
        cli.error(
            f"Task {task_id} must be in REVIEW state to perform audit.",
            hint="Move task to REVIEW: ./hammer tasks move <id> REVIEW",
        )
    current_path, _ = cli.find_task(task_id)
    task = FM.load(current_path)
    task_folder_name = os.path.basename(current_path)
    # the store writes the branch under 'Br'; parse_filename is the fallback
    # (same source ReviewDiffHook uses) so an alias typo cannot blank it.
    branch = task.metadata.get("Br") or parse_filename(task_folder_name)[1]
    review_dir = os.path.join(cli.tasks_path, "review")
    patches_dir = os.path.join(review_dir, task_folder_name, "patches")
    from ..audit import generate_file_patches, get_patch_snapshot, patches_are_fresh

    # A patch set that no longer matches the branch tip must be regenerated
    # even when Rc is PASSED: the md5s below would otherwise bind stale
    # content and the gate would attest to code that is not on the branch.
    snapshot = task.metadata.get("PatchSnapshot")
    stale = not snapshot or not patches_are_fresh(
        cli,
        branch,
        patches_dir,
        task.metadata.get("PatchFiles", []),
        snapshot,
    )
    if task.metadata.get("Rc") == "PASSED" and not stale:
        cli.log(
            f"✅ No changes detected for task {task_id} (already merged or empty diff). Skipping audit."
        )
        cli.finish({"id": task_id, "task_id": task_folder_name, "skipped": True})
        return
    if stale or not os.path.exists(patches_dir) or not os.listdir(patches_dir):
        try:
            patches = generate_file_patches(cli, str(task_id), current_path, branch)
            # Double-check - sometimes patches might not be written
            if (
                not patches
                or not os.path.exists(patches_dir)
                or not os.listdir(patches_dir)
            ):
                # Try one more time
                patches = generate_file_patches(cli, str(task_id), current_path, branch)
            if (
                not patches
                or not os.path.exists(patches_dir)
                or not os.listdir(patches_dir)
            ):
                cli.error("AUDIT_PATCH_MISSING", patches_dir=patches_dir)
            task.metadata["PatchFiles"] = patches
            task.metadata["PatchSnapshot"] = get_patch_snapshot(cli, branch)
            task.metadata["Reviewed"] = False
            task.metadata["Rc"] = ""
            reviews_path = os.path.join(review_dir, task_folder_name, "reviews.json")
            if os.path.exists(reviews_path):
                os.remove(reviews_path)
            FM.dump(task, current_path)
        except Exception:  # noqa: BLE001
            cli.error("AUDIT_PATCH_MISSING", patches_dir=patches_dir)
    output_path = os.path.join(review_dir, f"{task_folder_name}.audit")
    generate_audit(task_id, current_path, patches_dir, output_path)
    # Close out this task's review artifacts: the audit file and the patch it
    # verified would otherwise sit untracked in the shared store until some
    # other command's store-wide add swept them up.
    commit_task_paths(
        cli, os.path.join(review_dir, task_folder_name), f"Audit {task_id}", output_path
    )
    cli.log(f"✅ Audit log created for task {task_id}")
    cli.finish(
        {
            "id": task_id,
            "task_id": task_folder_name,
            "audit_path": output_path,
            "patches": task.metadata.get("PatchFiles", []),
        }
    )
