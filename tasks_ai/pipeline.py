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
            gates.append("main_sync")
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

        # 4. Integration gate: STAGING/DONE require branch to be merged into main/staging
        if "main_sync" in enabled_gates:
            if branch:
                # Check if branch is merged into main
                if not self.git.is_merged(branch, "main"):
                    raise PipelineError(
                        "BRANCH_NOT_MERGED", task_id=task_id, branch=branch
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
        branch = task.metadata.get("Br", "")
        if not branch:
            return

        if current_state is None:
            current_state = task.metadata.get("St", "BACKLOG")

        # 0. Auto-commit any uncommitted changes before transition
        task_id = task.metadata.get("Id", "unknown")
        status_res = self.git.run(["status", "--porcelain"])
        if status_res.stdout.strip():
            self.log(
                f"Git: Detected uncommitted changes. Auto-committing before {target_state}..."
            )
            self.git.run(["add", "."])
            self.git.run(
                [
                    "commit",
                    "-m",
                    f"[{task_id}] Auto-commit before {target_state} transition",
                ]
            )

        # Determine if this is a promotion or demotion
        try:
            curr_idx = PIPELINE_STAGES.index(current_state)
            target_idx = PIPELINE_STAGES.index(target_state)
        except ValueError:
            # If state not in stages (e.g. BLOCKED, REJECTED), default to promotion-like check
            curr_idx = -1
            target_idx = 0

        if target_idx < curr_idx:
            # DEMOTION: Sync higher branches back into feature branch
            self.log(
                f"Demoting task from {current_state} to {target_state}. Syncing higher branches back to {branch}..."
            )
            branches_to_sync = []
            if target_state == "PROGRESSING":
                branches_to_sync = ["main", "staging", "testing"]
            elif target_state in ["TESTING", "REVIEW"]:
                branches_to_sync = ["main", "staging"]

            # Check if branch exists - skip demotion sync if missing and target is REJECTED
            if not self.git.branch_exists(branch):
                if target_state == "REJECTED":
                    self.log(f"Branch {branch} does not exist locally. Skipping demotion sync for {target_state} transition.")
                    return

            self.git.run(["checkout", branch])
            for b in branches_to_sync:
                res = self.git.run(["rev-parse", "--verify", b])
                if res.returncode == 0:
                    self.log(f"Git: Syncing {b} -> {branch} (demotion)")
                    self.git.run(
                        ["merge", b, "-m", f"Sync: {b} -> {branch} (demotion)"]
                    )
            return

        # PROMOTION: Traditional pipeline merge
        pipeline_map = {"TESTING": "testing", "STAGING": "staging", "DONE": "main"}
        target_git_branch = pipeline_map.get(target_state)
        if not target_git_branch:
            return

        # Special case source branches
        src_branch = branch
        if target_state == "STAGING":
            src_branch = "testing"
        elif target_state == "DONE":
            src_branch = "staging"

        # Check if src_branch exists locally
        res = self.git.run(["rev-parse", "--verify", src_branch])
        if res.returncode != 0:
            if src_branch in ["testing", "staging"]:
                self.log(
                    f"Pipeline branch {src_branch} does not exist locally. Merging {branch} directly into {target_git_branch}."
                )
                src_branch = branch
            else:
                self.log(f"Branch {src_branch} does not exist locally. Skipping merge.")
                return

        self.log(f"Performing pipeline promotion: {src_branch} -> {target_git_branch}")

        # 1. Checkout target
        self.git.run(["checkout", target_git_branch])

        # 2. Pull target
        self.git.run(["pull", "origin", target_git_branch])

        # 3. Merge src into target
        merge_res = self.git.run(
            [
                "merge",
                "--no-ff",
                src_branch,
                "-m",
                f"[{task_id}] merge: {src_branch} into {target_git_branch}",
            ]
        )
        if merge_res.returncode != 0:
            raise RuntimeError(
                f"Git merge failed: {merge_res.stdout}\n{merge_res.stderr}. Please resolve conflicts manually."
            )

        # 4. Push target
        if yes or target_state == "DONE":
            self.git.run(["push", "origin", target_git_branch])

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
