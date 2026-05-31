import os


def run(cli, task_id, proof):
    task_path, state = cli.find_task(task_id)
    if not task_path or state != "REVIEW":
        cli.error(f"Task {task_id} must be in REVIEW state to perform verification.",
                  hint="Move task to REVIEW: ./hammer tasks move <id> REVIEW")

    review_dir = os.path.join(cli.tasks_path, "review")
    patches_dir = os.path.join(review_dir, task_id, "patches")
    task_folder_name = os.path.basename(task_path)
    audit_file = os.path.join(review_dir, f"{task_folder_name}.audit")
    
    if not os.path.exists(patches_dir) or not os.listdir(patches_dir):
        cli.error("AUDIT_PATCH_MISSING", patches_dir=patches_dir)
                  
    if not os.path.exists(audit_file):
        cli.error("AUDIT_MISSING", audit_path=audit_file, task_id=task_id)

    from ..audit import verify_audit
    if not verify_audit(patches_dir, audit_file):
        cli.error("AUDIT_MISMATCH", task_id=task_id)

    # Write the verification proof
    proof_path = os.path.join(task_path, "verification_proof.log")
    with open(proof_path, "w") as f:
        f.write(proof)
    
    # Update hash using pipeline
    cli.pipeline.update_audit_hash(task_id, task_path)
    
    cli.log(f"✅ Task {task_id} verified.")
