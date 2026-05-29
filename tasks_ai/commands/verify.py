import os
from ..audit import verify_audit


def run(cli, task_id, proof):
    patch_dir = ".tasks/review"
    patch_file = None
    audit_file = None
    for f in os.listdir(patch_dir):
        if f.startswith(task_id):
            if f.endswith(".patch"):
                patch_file = os.path.join(patch_dir, f)
            elif f.endswith(".audit"):
                audit_file = os.path.join(patch_dir, f)

    if not patch_file or not audit_file:
        cli.error(f"Patch or Audit file not found for task {task_id}")
        return

    if not verify_audit(patch_file, audit_file):
        cli.error(f"Audit verification failed for task {task_id}")
        return

    # Write the verification proof
    hash_path = audit_file.replace(".audit", ".audit_hash")
    with open(hash_path, "w") as f:
        f.write(proof)

    cli.log(f"✅ Task {task_id} verified.")
