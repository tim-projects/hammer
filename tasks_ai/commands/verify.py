import os


def run(cli, task_id, proof):
    task_path, state = cli.find_task(task_id)
    if not task_path or state != "REVIEW":
        cli.error(
            f"Task {task_id} must be in REVIEW state to perform verification.",
            hint="Move task to REVIEW: ./hammer tasks move <id> REVIEW",
        )

    # Get the *actual* current filepath, which holds the folder name
    current_path, _ = cli.find_task(task_id)
    task_folder_name = os.path.basename(current_path)

    review_dir = os.path.join(cli.tasks_path, "review")
    patches_dir = os.path.join(review_dir, task_folder_name, "patches")
    audit_file = os.path.join(review_dir, f"{task_folder_name}.audit")

    from ..file_manager import FM

    task = FM.load(task_path)
    is_auto_passed = task.metadata.get("Rc") == "PASSED"

    if not is_auto_passed:
        if not os.path.exists(patches_dir) or not os.listdir(patches_dir):
            cli.error("AUDIT_PATCH_MISSING", patches_dir=patches_dir)

        if not os.path.exists(audit_file):
            cli.error("AUDIT_MISSING", audit_path=audit_file, task_id=task_id)

        from ..audit import verify_audit

        if not verify_audit(task_path, patches_dir, audit_file):
            cli.error("AUDIT_MISMATCH", task_id=task_id)

    # Write the verification proof
    proof_path = os.path.join(task_path, "verification_proof.log")
    with open(proof_path, "w") as f:
        f.write(proof)

    # Update hash using pipeline if not auto-passed
    if not is_auto_passed:
        cli.pipeline.update_audit_hash(task_id, task_path)
    else:
        # If we skip, check_audit_integrity will be skipped anyway because Rc == "PASSED"
        cli.log(f"DEBUG: Skipping audit hash update for auto-passed task {task_id}")

    cli.log(f"✅ Task {task_id} verified.")
