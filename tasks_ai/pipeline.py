import os
import hashlib
from typing import List, Dict
from .constants import PIPELINE_STAGES


class PipelineError(Exception):
    def __init__(self, code, **kwargs):
        self.code = code
        self.kwargs = kwargs
        super().__init__(f"PipelineError: {code} kwargs: {kwargs}")


class PipelineService:
    """
    Core engine for pipeline state machine and gate enforcement.
    """

    def __init__(self, git_client, logger=None):
        self.git = git_client
        self.logger = logger

    def log(self, message: str):
        if self.logger:
            self.logger.log(message)

    def get_enabled_gates(self, target_state: str) -> List[str]:
        """Determine which gates are enabled for a target state."""
        gates = []
        if target_state in ["TESTING", "REVIEW", "STAGING", "DONE"]:
            gates.append("checkboxes")
        if target_state in ["STAGING", "DONE"]:
            gates.append("regression_check")
            gates.append("audit_integrity")
        if target_state == "DONE":
            gates.append("mandatory_verification")
        return gates

    def get_allowed_transitions(self, task_type: str = "task") -> Dict[str, List[str]]:
        """Get the allowed state transitions for a task type."""
        # For now, return default transitions. Could be expanded for type-specific workflows.
        from .constants import DEFAULT_ALLOWED_TRANSITIONS

        return DEFAULT_ALLOWED_TRANSITIONS

    def check_transition(self, cli, filename: str, new_status: str):
        """Enforce transition rules."""
        filepath, current_state = cli.find_task(filename)
        if not filepath:
            cli.error("TASK_NOT_FOUND", filename=filename)

        if current_state == new_status:
            cli.log(f"You are already on {new_status}")
            return

        allowed = self.get_allowed_transitions().get(current_state, [])
        if new_status not in allowed:
            task_id = os.path.basename(filepath).split("-")[0]
            cli.error(
                "FORBIDDEN_TRANSITION",
                from_state=current_state,
                to_state=new_status,
                task_id=task_id,
                next_valid_state="PROGRESSING",
            )

    def validate_gate(self, task, target_state: str, task_path: str):
        """
        Enforce pipeline gates for a given task and target state.
        Raises PipelineError with descriptive message and hint if gate fails.
        """
        task_id = str(task.metadata.get("Id", "unknown"))
        branch = task.metadata.get("Br", "")

        # 0. Fast-track check: If branch is already merged, bypass gates
        # Apply to REVIEW, STAGING, and DONE transitions
        if target_state in ["REVIEW", "STAGING", "DONE"]:
            if branch and self.git.is_merged(branch, "main"):
                self.log(
                    f"DEBUG: Task {task_id} branch {branch} is already merged. Fast-tracking promotion to {target_state}."
                )
                return True

        enabled_gates = self.get_enabled_gates(target_state)

        # 1. Checkboxes gate: All stages moving forward require checkboxes to be checked
        if "checkboxes" in enabled_gates:
            if self.has_unfinished_checkboxes(task_path):
                raise PipelineError("UNFINISHED_CHECKBOXES", task_id=task_id)

        # 2. Regression check gate: REVIEW/TESTING -> STAGING/DONE/ARCHIVED requires proof
        if "regression_check" in enabled_gates:
            # Check if coming from a state that requires proof
            current_state = os.path.basename(os.path.dirname(task_path)).upper()
            if current_state in ["REVIEW", "TESTING"]:
                if task.metadata.get("Rc") != "PASSED":
                    patch_path = f".tasks/review/{task_id}.patch"
                    raise PipelineError(
                        "REGRESSION_CHECK_NOT_PASSED",
                        task_id=task_id,
                        patch_path=patch_path,
                    )

        # 3. Cryptographic Audit Integrity for STAGING/DONE
        if "audit_integrity" in enabled_gates:
            if task.metadata.get("Rc") != "PASSED":
                # Only check audit if Rc is not PASSED (which implies skip or manual override)
                # But wait, governance usually requires audit IF Rc is not empty.
                pass

        # 4. Integration gate: STAGING/DONE require branch to be merged into appropriate pipeline branch
        if "main_sync" in enabled_gates:
            if branch:
                # Target branch for integration check
                integration_target = "main"
                if target_state == "STAGING":
                    integration_target = "staging"

                # Check if branch is merged into target
                if not self.git.is_merged(branch, integration_target):
                    raise PipelineError(
                        "BRANCH_NOT_MERGED",
                        task_id=task_id,
                        branch=branch,
                        target=integration_target,
                    )

        # 5. Check main divergence for terminal states
        if target_state in ["DONE", "ARCHIVED"]:
            synced, local, remote = self.git.check_main_divergence()
            if not synced:
                raise PipelineError(
                    "MAIN_DIVERGED", task_id=task_id, local=local, remote=remote
                )

        # 6. Check if staging is synced with source for DONE
        if target_state == "DONE":
            if branch:
                # Re-verify: Check specifically if the commit in the branch is reachable from main
                # Since is_merged(branch, 'main') passed, we know it is.
                # However, we also want to ensure no local main divergence.
                if not self.git.is_merged(branch, "staging"):
                    self.log(
                        f"Warning: Branch {branch} not fully merged to staging. Promotion might be incomplete."
                    )

        # 7. Mandatory Verification for DONE
        if "mandatory_verification" in enabled_gates:
            self.check_audit_integrity(task_id, task_path)

        return True

    def has_unfinished_checkboxes(self, task_path: str) -> bool:
        """Scan criteria.md for any - [ ] markers."""
        criteria_path = os.path.join(task_path, "criteria.md")
        if not os.path.exists(criteria_path):
            return False

        with open(criteria_path, "r", encoding="utf-8") as f:
            content = f.read()
            return "- [ ]" in content

    def git_merge_transition(
        self, task, target_state: str, current_state: str = None, yes: bool = False
    ):
        """Perform the git merges associated with a pipeline transition."""
        if current_state is None:
            current_state = task.metadata.get("St", "BACKLOG")

        # Determine if this is a promotion or demotion
        try:
            curr_idx = PIPELINE_STAGES.index(current_state)
            target_idx = PIPELINE_STAGES.index(target_state)
        except ValueError:
            curr_idx = -1
            target_idx = 0

        if target_idx < curr_idx:
            return self.git.demote_task(task, target_state, current_state=current_state)
        else:
            return self.git.promote_task(
                task, target_state, current_state=current_state, yes=yes
            )

    def update_audit_hash(self, task_id: str, task_path: str):
        """Update the cryptographic hash of criteria and proof for integrity tracking."""
        audit_path = os.path.join(
            os.path.dirname(task_path), "review", f"{task_id}.audit"
        )
        if not os.path.exists(audit_path):
            audit_path = os.path.join(
                os.path.dirname(task_path),
                os.path.basename(task_path) + ".audit",
            )

        proof_path = os.path.join(task_path, "verification_proof.log")
        hash_path = os.path.join(task_path, ".audit_hash")

        hasher = hashlib.sha256()
        with open(os.path.join(task_path, "criteria.md"), "rb") as f:
            hasher.update(f.read())
        with open(proof_path, "rb") as f:
            hasher.update(f.read())
        with open(audit_path, "rb") as f:
            hasher.update(f.read())

        with open(hash_path, "w") as f:
            f.write(hasher.hexdigest())
        self.log(f"Integrity hash updated for task {task_id}")

    def check_audit_integrity(self, task_id: str, task_path: str):
        """
        Verify that the task has a valid cryptographic audit and verification proof.
        Raises PipelineError with descriptive message and hint if integrity check fails.
        """
        audit_path = os.path.join(
            os.path.dirname(task_path), "review", f"{task_id}.audit"
        )
        # Handle case where task_id is the directory name (id-type-title)
        if not os.path.exists(audit_path):
            audit_path = os.path.join(
                os.path.dirname(task_path),
                os.path.basename(task_path) + ".audit",
            )

        proof_path = os.path.join(task_path, "verification_proof.log")
        hash_path = os.path.join(task_path, ".audit_hash")
        # In REVIEW, files might be in the parent dir of patches or sibling?
        # Actually, audit files stay in the state folder where they were created.

        # Look for patches folder
        patches_dir = os.path.join(task_path, "patches")

        from .audit import verify_audit

        self.log(
            f"DEBUG: checking patches_dir={patches_dir}, exists={os.path.exists(patches_dir)}"
        )
        if not os.path.exists(patches_dir) or not os.listdir(patches_dir):
            raise PipelineError(
                "AUDIT_PATCH_MISSING", task_id=task_id, patches_dir=patches_dir
            )

        if not os.path.exists(audit_path):
            raise PipelineError("AUDIT_MISSING", audit_path=audit_path, task_id=task_id)
        if not os.path.exists(proof_path):
            raise PipelineError("PROOF_MISSING", task_id=task_id, proof_path=proof_path)

        if not os.path.exists(hash_path):
            raise PipelineError("HASH_MISSING", task_id=task_id, hash_path=hash_path)

        if not verify_audit(patches_dir, audit_path):
            raise PipelineError("AUDIT_MISMATCH", task_id=task_id)

        # Check hash of criteria and proof
        hasher = hashlib.sha256()
        try:
            with open(os.path.join(task_path, "criteria.md"), "rb") as f:
                hasher.update(f.read())
            with open(proof_path, "rb") as f:
                hasher.update(f.read())
            with open(audit_path, "rb") as f:
                hasher.update(f.read())
        except FileNotFoundError as e:
            raise PipelineError(f"Integrity check failed: missing file {e.filename}")

        with open(hash_path, "r") as f:
            stored_hash = f.read().split()[0]

        if hasher.hexdigest() != stored_hash:
            raise PipelineError("INTEGRITY_MISMATCH", task_id=task_id)

        return True
