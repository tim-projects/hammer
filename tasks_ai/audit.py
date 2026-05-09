
import hashlib
import json
import os

def generate_audit(task_id, patch_path, output_path):
    with open(patch_path, "rb") as f:
        diff_hash = hashlib.sha256(f.read()).hexdigest()
    
    audit_data = {
        "task_id": task_id,
        "patch_hash": diff_hash,
        "status": "verified"
    }
    
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
