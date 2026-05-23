<<<<<<< HEAD
import json
import hashlib
import os


def generate_audit(task_id, diff_path, output_path):
    if not os.path.exists(diff_path):
        return {"error": "Diff patch not found"}

    with open(diff_path, "rb") as f:
        diff_hash = hashlib.sha256(f.read()).hexdigest()

    audit_data = {
        "task_id": task_id,
        "diff_hash": diff_hash,
        "status": "audited",
        "timestamp": os.path.getmtime(diff_path),
    }

    with open(output_path, "w") as f:
        json.dump(audit_data, f, indent=4)

    return audit_data


def verify_audit(task_id, diff_path, audit_path):
    if not os.path.exists(audit_path):
        return False
    with open(audit_path, "r") as f:
        audit_data = json.load(f)
    if audit_data.get("task_id") != task_id:
        return False
    with open(diff_path, "rb") as f:
        current_hash = hashlib.sha256(f.read()).hexdigest()
    return audit_data.get("diff_hash") == current_hash
=======
import hashlib
import json
import os


def generate_audit(task_id, patch_path, output_path):
    with open(patch_path, "rb") as f:
        diff_hash = hashlib.sha256(f.read()).hexdigest()

    audit_data = {"task_id": task_id, "patch_hash": diff_hash, "status": "verified"}

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(audit_data, f, indent=4)
    print(f"Audit file generated at {output_path}")


def verify_audit(patch_path, audit_path):
    if not os.path.exists(audit_path):
        return False
    with open(patch_path, "rb") as f:
        current_hash = hashlib.sha256(f.read()).hexdigest()
    with open(audit_path, "r") as f:
        audit_data = json.load(f)
    return audit_data["patch_hash"] == current_hash
>>>>>>> testing
