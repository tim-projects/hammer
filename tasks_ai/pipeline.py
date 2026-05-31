import os
import hashlib
import re
from .constants import get_workflows, DEFAULT_ALLOWED_TRANSITIONS
from .utils import parse_filename

class PipelineError(Exception):
    def __init__(self, code, **kwargs):
        self.code = code
        self.kwargs = kwargs
        super().__init__(f"PipelineError: {code} kwargs: {kwargs}")


class PipelineService:
    """
    Service for enforcing pipeline gates and handling state transitions.
    Decoupled from CLI display logic.
    """

    def __init__(self, context, git_client, logger=None):
        self.context = context
        self.git = git_client
        self.logger = logger
        self.workflows = get_workflows(context.tasks_path)

    def get_allowed_transitions(self, task_type: str):
        workflow = self.workflows.get(task_type, self.workflows.get("default", {"transitions": DEFAULT_ALLOWED_TRANSITIONS}))
        return workflow.get("transitions", DEFAULT_ALLOWED_TRANSITIONS)

    def log(self, message: str):
        if self.logger:
            self.logger.log(message)

    def check_transition(self, cli, filename: str, new_status: str):
        filepath, current_state = cli.find_task(filename)
        if not filepath or current_state is None:
            return
        
        task_type, _ = parse_filename(os.path.basename(filepath))
        allowed_transitions = self.get_allowed_transitions(task_type)
        
        # Allow multi-step moves: validate each step in the chain
        if "," in new_status:
            last_state = current_state
            for next_state in new_status.split(","):
                next_state = next_state.strip()
                if next_state == last_state:
                    continue
                if next_state not in allowed_transitions.get(last_state, []):
                     cli.error(
                        f"Forbidden transition in chain: {last_state} -> {next_state}",
                        hint=f"Allowed from {last_state}: {', '.join(allowed_transitions.get(last_state, []))}",
                    )
                     return
                last_state = next_state
            return
        
        if (
            new_status not in allowed_transitions.get(current_state, [])
            and current_state != new_status
        ):
            if current_state == "BACKLOG" and new_status == "PROGRESSING":
                cli.log("Auto-promoting BACKLOG to READY before PROGRESSING.")
                cli._move_logic(filename, "READY", yes=True)
                return
            cli.error(
                f"Forbidden transition: {current_state} -> {new_status}",
                hint=f"Allowed: {', '.join(allowed_transitions.get(current_state, []))}",
            )

    def validate_gate(self, task, target_state: str, task_path: str):
        """
        Enforce pipeline gates for a given task and target state.
        Raises PipelineError with descriptive message and hint if gate fails.
        """
        task_id = task.metadata.get("Id")
        task_type, _ = parse_filename(os.path.basename(task_path))
        
        # Resolve gates based on workflow
        workflow = self.workflows.get(task_type, self.workflows.get("default", {}))
        gates_config = workflow.get("gates", {})
        enabled_gates = gates_config.get(target_state, [])

        # 1. Enforce criteria completion for TESTING
        if "incomplete_checkboxes" in enabled_gates and self.has_incomplete_checkboxes(task_path):
            raise PipelineError("UNFINISHED_CHECKBOXES")

        # 2. Regression check gate: REVIEW/TESTING -> STAGING/DONE/ARCHIVED requires Rc to be set
        if "regression_check" in enabled_gates:
            # Check if coming from a state that requires Rc
            current_state = os.path.basename(os.path.dirname(task_path)).upper()
            if current_state in ["REVIEW", "TESTING", "STAGING", "DONE"]:
                if not task.metadata.get("Rc"):
                    patch_path = f".tasks/review/{task_id}.patch"
                    raise PipelineError(
                        "REGRESSION_CHECK_NOT_PASSED",
                        patch_path=patch_path,
                        task_id=task_id
                    )

        # 3. Cryptographic Audit Integrity for STAGING/DONE
        if "audit_integrity" in enabled_gates:
            self.check_audit_integrity(task_id, task_path)

        # 4. Merge verification for DONE/ARCHIVED
        if "merge_check" in enabled_gates:
            branch = task.metadata.get("Br", "")
            if branch:
                # Check if branch is merged into main
                if not self.git.is_merged(branch, "main"):
                    raise PipelineError(
                        "BRANCH_NOT_MERGED",
                        branch=branch
                    )

    def git_merge_transition(self, task, target_state: str, yes: bool = False):
        """Perform the git merges associated with a pipeline transition."""
        branch = task.metadata.get("Br", "")
        if not branch:
            return

        pipeline_map = {"TESTING": "testing", "STAGING": "staging", "DONE": "main"}

        target_git_branch = pipeline_map.get(target_state)
        if not target_git_branch:
            return

        # Special case: task -> testing
        src_branch = branch
        if target_state == "STAGING":
            src_branch = "testing"
        elif target_state == "DONE":
            src_branch = "staging"

        # Check if src_branch exists locally
        res = self.git.run(["rev-parse", "--verify", src_branch])
        if res.returncode != 0:
            self.log(f"Branch {src_branch} does not exist locally. Skipping merge.")
            return

        self.log(f"Performing pipeline merge: {src_branch} -> {target_git_branch}")

        # 1. Checkout target
        self.git.run(["checkout", target_git_branch])

        # 2. Pull target
        self.git.run(["pull", "origin", target_git_branch])

        # 3. Merge src into target
        merge_res = self.git.run(
            ["merge", src_branch, "-m", f"merge: {src_branch} into {target_git_branch}"]
        )
        if merge_res.returncode != 0:
            raise RuntimeError(
                f"Git merge failed: {merge_res.stderr}. Please resolve conflicts manually."
            )

        # 4. Push target
        if yes:
            self.git.run(["push", "origin", target_git_branch])
        else:
            self.log(
                f"Merge successful. Manual 'git push origin {target_git_branch}' required or use -y."
            )

    def has_incomplete_checkboxes(self, task_path: str) -> bool:
        if not os.path.isdir(task_path):
            return False
        for filename in os.listdir(task_path):
            if not filename.endswith(".md"):
                continue
            filepath = os.path.join(task_path, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            # Allow flexible whitespace around - and [ ]
            if re.search(r"^\s*-\s*\[\s*\]", content, re.MULTILINE):
                return True
        return False

    def update_audit_hash(self, task_id: str, task_path: str):
        # Sibling files reside in the same directory as the criteria.md, proof, etc.
        criteria_path = os.path.join(task_path, "criteria.md")
        self.log(f"DEBUG: update_audit_hash task_path={task_path}, criteria_path={criteria_path}, exists={os.path.exists(criteria_path)}")
        proof_path = os.path.join(task_path, "verification_proof.log")
        hash_path = os.path.join(task_path, ".audit_hash")
        
        # Sibling files (patch/audit) are in .tasks/review/FOLDER_NAME/
        review_dir = os.path.dirname(task_path)
        task_folder_name = os.path.basename(task_path)
        audit_path = os.path.join(review_dir, f"{task_folder_name}.audit")

        hasher = hashlib.md5()
        with open(criteria_path, "rb") as f_crit, \
             open(proof_path, "rb") as f_proof, \
             open(audit_path, "rb") as f_audit:
            hasher.update(f_crit.read())
            hasher.update(f_proof.read())
            hasher.update(f_audit.read())

        with open(hash_path, "w") as f:
            f.write(hasher.hexdigest())

    def check_audit_integrity(self, task_id: str, task_path: str):
        """
        Verify the integrity of the cryptographic audit and verification proof.
        Raises PipelineError with descriptive message and hint if integrity check fails.
        """
        criteria_path = os.path.join(task_path, "criteria.md")
        proof_path = os.path.join(task_path, "verification_proof.log")
        hash_path = os.path.join(task_path, ".audit_hash")
        
        # Sibling files (patch folder/audit file) are in .tasks/review/FOLDER_NAME/
        review_dir = os.path.join(self.context.tasks_path, "review")
        task_folder_name = os.path.basename(task_path)
        patches_dir = os.path.abspath(os.path.join(review_dir, task_folder_name, "patches"))
        audit_path = os.path.abspath(os.path.join(review_dir, f"{task_folder_name}.audit"))
        
        abs_task_path = os.path.abspath(task_path)

        # 1. Check for basic files
        self.log(f"DEBUG: checking patches_dir={patches_dir}, exists={os.path.exists(patches_dir)}")
        if not os.path.exists(patches_dir) or not os.listdir(patches_dir):
             raise PipelineError("AUDIT_PATCH_MISSING", patches_dir=patches_dir)
            
        if not os.path.exists(audit_path):
            raise PipelineError("AUDIT_MISSING", audit_path=audit_path, task_id=task_id)

        if not os.path.exists(proof_path):
            raise PipelineError("PROOF_MISSING", proof_path=proof_path)

        if not os.path.exists(hash_path):
            raise PipelineError("HASH_MISSING", hash_path=hash_path)

        # 2. Verify Audit vs Patches
        from .audit import verify_audit
        if not verify_audit(patches_dir, audit_path):
             raise PipelineError("AUDIT_MISMATCH", task_id=task_id)

        # 3. Verify Integrity Hash (Criteria + Proof + Audit)
        hasher = hashlib.md5()
        try:
            with open(criteria_path, "rb") as f_crit, \
                 open(proof_path, "rb") as f_proof, \
                 open(audit_path, "rb") as f_audit:
                hasher.update(f_crit.read())
                hasher.update(f_proof.read())
                hasher.update(f_audit.read())
        except FileNotFoundError as e:
            raise PipelineError(f"Integrity check failed: missing file {e.filename}")

        with open(hash_path, "r") as f:
            stored_hash = f.read().split()[0]

        if hasher.hexdigest() != stored_hash:
             raise PipelineError("INTEGRITY_MISMATCH", task_id=task_id)
        
        return True
