import os
import hashlib
import re

class PipelineError(Exception):
    def __init__(self, message, hint=None):
        super().__init__(message)
        self.hint = hint

class PipelineService:
    """
    Service for enforcing pipeline gates and handling state transitions.
    Decoupled from CLI display logic.
    """
    def __init__(self, context, git_client, logger=None):
        self.context = context
        self.git = git_client
        self.logger = logger

    def log(self, message: str):
        if self.logger:
            self.logger.log(message)

    def check_transition(self, cli, filename: str, new_status: str):
        from .constants import ALLOWED_TRANSITIONS
        filepath, current_state = cli.find_task(filename)
        if not filepath or current_state is None:
            return
        if "," in new_status:
            return
        if (
            new_status not in ALLOWED_TRANSITIONS.get(current_state, [])
            and current_state != new_status
        ):
            if current_state == "BACKLOG" and new_status == "PROGRESSING":
                cli.log("Auto-promoting BACKLOG to READY before PROGRESSING.")
                cli.log("REMINDER: Ensure the task is fully populated with 'story', 'tech', 'criteria', and 'plan' fields to meet the READY gate.")
                cli._move_logic(filename, "READY", yes=True)
                return
            cli.error(f"Forbidden transition: {current_state} -> {new_status}")

    def validate_gate(self, task, target_state: str, task_path: str):
        """
        Enforce pipeline gates for a given task and target state.
        Raises PipelineError with descriptive message and hint if gate fails.
        """
        task_id = task.metadata.get("Id")
        
        # 1. Enforce criteria completion for TESTING
        if target_state == "TESTING" and self.has_incomplete_checkboxes(task_path):
             raise PipelineError(
                 f"Cannot move to {target_state}: contains unfinished checkboxes (- [ ])",
                 hint="Edit criteria.md and change '- [ ]' to '- [x]' for completed items."
             )

        # 2. Regression check gate: REVIEW/TESTING -> STAGING/DONE/ARCHIVED requires Rc to be set
        if target_state in ["STAGING", "DONE", "ARCHIVED"]:
            # Check if coming from a state that requires Rc
            current_state = os.path.basename(os.path.dirname(task_path)).upper()
            if current_state in ["REVIEW", "TESTING", "STAGING", "DONE"]:
                if not task.metadata.get("Rc"):
                     patch_path = f".tasks/review/{task_id}.patch"
                     raise PipelineError(
                         f"Cannot move to {target_state}: regression check not passed (Rc flag not set).",
                         hint=f"Complete the regression check before promoting.\n"
                              f"  1. Review the diff patch at {patch_path}\n"
                              "  2. Audit for regressions and side-effects\n"
                              f"  3. Run: ./hammer tasks modify {task_id} --regression-check"
                     )

        # 3. Cryptographic Audit Integrity for STAGING/DONE
        if target_state in ["STAGING", "DONE"]:
            if not self.check_audit_integrity(task_id, task_path):
                 raise PipelineError(
                     f"Task '{task_id}' failed cryptographic audit integrity check.",
                     hint="The criteria or proof has changed since the last audit. Re-run 'tasks audit' and 'tasks verify'."
                 )

        # 4. Merge verification for DONE/ARCHIVED
        if target_state in ["DONE", "ARCHIVED"]:
            branch = task.metadata.get("Br", "")
            if branch:
                # Check if branch is merged into main
                if not self.git.is_merged(branch, "main"):
                     raise PipelineError(
                         f"Task '{task_id}' cannot be moved to {target_state} as branch '{branch}' is not merged into 'main'.",
                         hint="Run './hammer repo merge <branch> main' to finalize integration."
                     )

    def git_merge_transition(self, task, target_state: str, yes: bool = False):
        """Perform the git merges associated with a pipeline transition."""
        branch = task.metadata.get("Br", "")
        if not branch:
            return

        pipeline_map = {
            "TESTING": "testing",
            "STAGING": "staging",
            "DONE": "main"
        }
        
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
        merge_res = self.git.run(["merge", src_branch, "-m", f"merge: {src_branch} into {target_git_branch}"])
        if merge_res.returncode != 0:
            raise RuntimeError(f"Git merge failed: {merge_res.stderr}. Please resolve conflicts manually.")
            
        # 4. Push target
        if yes:
            self.git.run(["push", "origin", target_git_branch])
        else:
            self.log(f"Merge successful. Manual 'git push origin {target_git_branch}' required or use -y.")

    def has_incomplete_checkboxes(self, task_path: str) -> bool:
        if not os.path.isdir(task_path):
            return False
        for filename in os.listdir(task_path):
            if not filename.endswith(".md"):
                continue
            filepath = os.path.join(task_path, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            if re.search(r"^- \[ \]", content, re.MULTILINE):
                return True
        return False


    def update_audit_hash(self, task_id: str, task_path: str):
        criteria_path = os.path.join(task_path, "criteria.md")
        proof_path = os.path.join(task_path, "verification_proof.log")
        hash_path = os.path.join(task_path, ".audit_hash")

        hasher = hashlib.sha256()
        with open(criteria_path, "rb") as f1, open(proof_path, "rb") as f2:
            hasher.update(f1.read())
            hasher.update(f2.read())

        with open(hash_path, "w") as f:
            f.write(hasher.hexdigest())

    def check_audit_integrity(self, task_id: str, task_path: str) -> bool:
        criteria_path = os.path.join(task_path, "criteria.md")
        proof_path = os.path.join(task_path, "verification_proof.log")
        hash_path = os.path.join(task_path, ".audit_hash")

        if not os.path.exists(hash_path):
            return False

        hasher = hashlib.md5()
        try:
            with open(criteria_path, "rb") as f1, open(proof_path, "rb") as f2:
                hasher.update(f1.read())
                hasher.update(f2.read())
        except FileNotFoundError:
            return False

        with open(hash_path, "r") as f:
            stored_hash = f.read().split()[0]

        return hasher.hexdigest() == stored_hash
