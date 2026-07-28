import os
import shutil
from datetime import datetime
from .hooks import PipelineHook
from .constants import CURRENT_TASK_FILENAME
from .models import Task
from .utils import parse_filename


class TaskRepairHook(PipelineHook):
    """Resets governance metadata when a task is moved to PROGRESSING."""

    def execute(self, cli, task, current_state, new_status, filepath):
        if new_status == "PROGRESSING":
            cli.log(
                f"DEBUG: Repairing task {task.metadata.get('Id')} metadata (demotion to PROGRESSING)."
            )
            # Explicitly reset sensitive governance flags
            task.metadata["Reviewed"] = False
            task.metadata["Rc"] = ""
            task.metadata["AuditPassed"] = False
            task.metadata["PatchGenTime"] = None
            task.metadata["DoneAt"] = None

            # Save the repaired metadata
            cli._atomic_write(filepath, task)


class SaveProgressHook(PipelineHook):
    """Saves progress notes to current-task.md in the task directory."""

    def execute(self, cli, task, current_state, new_status, filepath):
        if not os.path.isdir(filepath):
            return
        dump_path = os.path.join(filepath, CURRENT_TASK_FILENAME)
        d = Task(
            metadata={"Task": os.path.basename(filepath)},
            parts={"content": task.parts.get("notes", "- Progress: \n")},
        )
        cli._atomic_write(dump_path, d)


class ValidationHook(PipelineHook):
    """Runs all validation checks when exiting PROGRESSING or TESTING."""

    def execute(self, cli, task, current_state, new_status, filepath):
        if current_state in ["PROGRESSING", "TESTING"]:
            cli.console(
                "validate", "pre-transition", f"{current_state} -> {new_status}"
            )

            # Enforce presence of essential files
            for required_file in ["criteria.md", "progress.md"]:
                if not os.path.exists(os.path.join(filepath, required_file)):
                    cli.error(
                        f"WHAT: Missing {required_file} | WHY: Pipeline governance requires {required_file} to be present | HOW: Run 'touch {os.path.join(filepath, required_file)}' to create the file | CONSEQUENCE: Transition halted."
                    )

            # Temporarily disable JSON mode to prevent early exit during transition
            # run_tool calls cli.error (which sys.exits) on failure
            orig_json = cli.as_json
            cli.as_json = False
            try:
                cli.run_tool("all")
            finally:
                cli.as_json = orig_json

            # If we reach here, all checks passed
            task.metadata["Tp"] = True
            cli._atomic_write(filepath, task)


class ContentSufficiencyHook(PipelineHook):
    """Checks if the task has enough content to leave BACKLOG or enter PROGRESSING."""

    def execute(self, cli, task, current_state, new_status, filepath):
        def has_complete_content(t, fn):
            for part in ["story", "tech", "criteria", "plan"]:
                if not t.parts.get(part) or len(str(t.parts.get(part)).strip()) < 10:
                    return False
            tt, _ = parse_filename(fn)
            if tt == "issue" and (
                not t.parts.get("repro") or len(str(t.parts.get("repro")).strip()) < 10
            ):
                return False
            return True

        if current_state == "BACKLOG" and new_status not in ("BACKLOG", "REJECTED"):
            if not has_complete_content(task, os.path.basename(filepath)):
                cli.error("Task lacks required content to leave BACKLOG.")

        if new_status == "PROGRESSING":
            if not has_complete_content(task, os.path.basename(filepath)):
                cli.error("Task lacks sufficient detail to move to PROGRESSING.")


class BlockerCheckHook(PipelineHook):
    """Checks for active blockers before entering PROGRESSING."""

    def execute(self, cli, task, current_state, new_status, filepath):
        if new_status == "PROGRESSING":
            bl = task.metadata.get("Bl", [])
            for b in bl:
                _, bs = cli.find_task(str(b))
                if bs != "ARCHIVED":
                    cli.error(f"Blocked by {b}. Blocker must be ARCHIVED first.")


class TestingToReviewGateHook(PipelineHook):
    """Enforces gates when moving from TESTING to REVIEW."""

    def execute(self, cli, task, current_state, new_status, filepath):
        if current_state == "TESTING" and new_status == "REVIEW":
            if not task.metadata.get("Tp", False):
                cli.error(
                    "Tests must be passed before moving to REVIEW.",
                    hint="Run 'hammer tasks modify <id> --tests-passed' to mark tests as passed.",
                )

            # Robust check: if patches is empty, auto-pass regression check
            # Rc is managed by ReviewDiffHook now
            task_id = task.metadata.get("Id")
            task.metadata["Rc"] = ""
            # Record generation time
            task.metadata["PatchGenTime"] = datetime.now().timestamp()

            cli.log(
                f"DEBUG: TestingToReviewGateHook: task.metadata['Rc'] = {task.metadata.get('Rc')}"
            )
            cli._atomic_write(filepath, task)
            cli.console("gate", "review", "entered")

            # PHASE 1: Manual Review
            cli.log(
                f"💡 HINT: Manual patch review required.\n"
                f"1. Review all patches in: '.tasks/review/{os.path.basename(filepath)}/patches/'\n"
                f"2. Mark review complete: './hammer tasks modify {task_id} --reviewed'\n"
                f"Once reviewed, you will be prompted to run audit and regression check."
            )


class BranchCheckHook(PipelineHook):
    """Handles branch restoration and remote push verification."""

    def execute(self, cli, task, current_state, new_status, filepath):
        _, branch = parse_filename(os.path.basename(filepath))
        has_origin = cli._run_git(["remote", "get-url", "origin"]).returncode == 0

        # Restoration check
        if new_status == "PROGRESSING":
            branch_sha_res = cli._run_git(["rev-parse", branch])
            branch_sha = (
                branch_sha_res.stdout.strip() if branch_sha_res.returncode == 0 else ""
            )
            if not branch_sha:
                if has_origin:
                    remote_check = cli._run_git(
                        ["ls-remote", "--heads", "origin", branch]
                    )
                    if remote_check.stdout.strip():
                        cli.console("git", "restore", f"{branch} from origin")
                        cli._run_git(
                            ["checkout", "-b", branch, f"origin/{branch}"], cwd=cli.root
                        )

        # Remote push check
        if new_status in ("REVIEW", "STAGING", "DONE", "ARCHIVED"):
            if has_origin:
                if not cli._run_git(["ls-remote", "--heads", "origin", branch]).stdout:
                    cli.error("BRANCH_NOT_PUSHED", branch=branch)


class ReviewDiffHook(PipelineHook):
    """Ensures file-level diff patches are generated when entering REVIEW."""

    def execute(self, cli, task, current_state, new_status, filepath):
        if new_status == "REVIEW":
            cli.log(
                f"DEBUG: ReviewDiffHook triggered for task {task.metadata.get('Id')}. Ensuring patches exist."
            )
            from .audit import generate_file_patches

            _, branch = parse_filename(os.path.basename(filepath))
            task_id = task.metadata.get("Id")

            # Check if patches exist on disk and metadata is populated

            # Idempotent patch generation
            patches = generate_file_patches(cli, str(task_id), filepath, branch)
            task.metadata["PatchFiles"] = patches
            cli._atomic_write(filepath, task)
            cli.log("DEBUG: ReviewDiffHook: patches verified and generated.")


class ArchivedCommitHook(PipelineHook):
    """Commits and pushes the tasks worktree when entering ARCHIVED."""

    def execute(self, cli, task, current_state, new_status, filepath):
        if new_status == "ARCHIVED":
            cli._run_git(["add", "--all"], cwd=cli.tasks_path)
            cli._run_git(
                [
                    "commit",
                    "-m",
                    f"Archive [{task.metadata.get('Id')}] {task.metadata.get('Ti')}",
                ],
                cwd=cli.tasks_path,
            )
            try:
                cli._push_tasks_branch("tasks", fatal=False)
            except Exception:
                pass


class PostMoveCommitHook(PipelineHook):
    """Standard commit for non-archived moves."""

    def execute(self, cli, task, current_state, new_status, filepath):
        if new_status != "ARCHIVED":
            cli._run_git(["add", "--all"], cwd=cli.tasks_path)
            cli._run_git(
                [
                    "commit",
                    "--allow-empty",
                    "-m",
                    f"Mv {os.path.basename(filepath)} -> {new_status}",
                ],
                cwd=cli.tasks_path,
            )


class ValidationPassedMarkHook(PipelineHook):
    """Marks validation_passed (Vp) when entering TESTING or leaving TESTING for other states (except REVIEW)."""

    def execute(self, cli, task, current_state, new_status, filepath):
        updated = False
        if current_state == "PROGRESSING" and new_status == "TESTING":
            cli.console("validate", "pass", "marking validation_passed")
            task.metadata["Vp"] = True
            updated = True

        if current_state == "TESTING" and new_status != "REVIEW":
            task.metadata["Vp"] = True
            updated = True

        if updated:
            cli._atomic_write(filepath, task)


class CleanWorkspaceHook(PipelineHook):
    """Ensures no debug logs or temp files remain in the workspace."""

    def execute(self, cli, task, current_state, new_status, filepath):
        cli.console("clean", "workspace", f"transition to {new_status}")
        # Define patterns to clean
        patterns = [
            "*.log",
            "__pycache__",
            ".pytest_cache",
            ".ruff_cache",
            ".tasks.bak_*",
        ]
        for pattern in patterns:
            cli.console("clean", "pattern", pattern)
            # Only clean in the project root, NOT inside .tasks/review
            cli.git.run(
                [
                    "clean",
                    "-fd",
                    "-e",
                    ".tasks/review",
                    "-e",
                    ".tasks",
                    "-e",
                    ".env",
                    "--",
                    pattern,
                ]
            )


class BranchSyncHook(PipelineHook):
    """Switches to the task branch and merges changes from main."""

    def execute(self, cli, task, current_state, new_status, filepath):
        if new_status == "PROGRESSING":
            _, branch = parse_filename(os.path.basename(filepath))
            if not branch:
                return

            cli.console("git", "sync", f"{branch} with main")

            # 1. Checkout the branch
            checkout_res = cli.git.run(["checkout", branch])
            if checkout_res.returncode != 0:
                cli.error("BRANCH_CHECKOUT_FAIL", branch=branch)

            # 2. Fetch latest main
            default_branch = cli.git.get_default_branch()
            fetch_res = cli.git.run(["fetch", "origin", default_branch], check=False)

            # 3. Determine merge source: prefer origin/default_branch, fallback to local default_branch
            merge_source = f"origin/{default_branch}"
            if fetch_res.returncode != 0:
                local_res = cli.git.run(["rev-parse", "--verify", default_branch], check=False)
                if local_res.returncode == 0:
                    merge_source = default_branch
                else:
                    cli.console("git", "sync", "skipped (no remote/main)")
                    return

            # 4. Attempt merge
            merge_res = cli.git.run(["merge", merge_source])
            if merge_res.returncode != 0:
                cli.console("git", "merge", "conflict")
                cli.git.run(["merge", "--abort"])
                cli.error("MERGE_CONFLICT", branch=branch, default=default_branch)

            cli.console("git", "sync", "complete")


class MainBranchProtectionHook(PipelineHook):
    """Prevents transitions if the user is working directly on the main branch."""

    def execute(self, cli, task, current_state, new_status, filepath):
        # We only care about blocking work if they are trying to progress or move towards completion
        if new_status in ["PROGRESSING", "TESTING", "REVIEW", "STAGING", "DONE"]:
            current_git_branch = cli.git.get_current_branch()
            default_branch = cli.git.get_default_branch()

            if current_git_branch == default_branch:
                cli.error(
                    "MAIN_BRANCH_PROTECTION",
                    new_status=new_status,
                    default_branch=default_branch,
                )


class ProgressUpdateHook(PipelineHook):
    """Enforces that progress notes have been updated before exiting PROGRESSING."""

    def execute(self, cli, task, current_state, new_status, filepath):
        if current_state == "PROGRESSING" and new_status != "PROGRESSING":
            progress_path = os.path.join(filepath, "progress.md")
            current_path = os.path.join(filepath, CURRENT_TASK_FILENAME)

            # Use progress.md if it exists, otherwise current-task.md
            progress_file = progress_path
            if not os.path.exists(progress_file):
                progress_file = current_path

            if not os.path.exists(progress_file):
                cli.error(
                    f"No progress tracking file found (checked {progress_path} and {current_path})."
                )

            # Get last commit version of the file
            _, branch = parse_filename(os.path.basename(filepath))
            git_res = cli.git.run(
                ["show", f"HEAD:{os.path.relpath(progress_file, cli.tasks_path)}"],
                capture=True,
            )

            if git_res.returncode == 0:
                last_content = git_res.stdout.strip()
                with open(progress_file, "r") as f:
                    current_content = f.read().strip()

                if last_content == current_content:
                    cli.error(
                        "NO_PROGRESS_UPDATE",
                        progress_path=progress_path,
                        current_path=current_path,
                    )


class BranchSyncOnExitTestingHook(PipelineHook):
    """Detect and merge missing commit during exit TESTING."""

    def execute(self, cli, task, current_state, new_status, filepath):
        if current_state == "TESTING" and new_status != "TESTING":
            _, branch = parse_filename(os.path.basename(filepath))

            # Detect divergence
            default_branch = cli.git.get_default_branch()
            cli.console("git", "check", "divergence")
            res = cli.git.run(["rev-list", f"{default_branch}..{branch}", "--count"])
            if res.stdout.strip() != "0":
                cli.console("git", "merge", "missing commit")
                cli.git.run(["merge", default_branch])


class CleanupReviewArtifactsHook(PipelineHook):
    """Clears review artifacts (patches, audit files, Rc flag) when moving back to early states."""

    def execute(self, cli, task, current_state, new_status, filepath):
        if new_status in ["BACKLOG", "READY", "PROGRESSING"]:
            task_folder_name = os.path.basename(filepath)

            # 1. Clear patches directory
            patches_dir = os.path.join(
                cli.tasks_path, "review", task_folder_name, "patches"
            )
            if os.path.exists(patches_dir):
                cli.log(f"DEBUG: Cleaning up patches directory: {patches_dir}")
                shutil.rmtree(patches_dir)

            # 2. Clear audit file
            audit_path = os.path.join(
                cli.tasks_path, "review", f"{task_folder_name}.audit"
            )
            if os.path.exists(audit_path):
                cli.log(f"DEBUG: Cleaning up audit file: {audit_path}")
                os.remove(audit_path)

            # 3. Clear verification proof and internal audit hash in task folder
            proof_path = os.path.join(filepath, "verification_proof.log")
            if os.path.exists(proof_path):
                cli.log(f"DEBUG: Cleaning up verification proof: {proof_path}")
                os.remove(proof_path)

            hash_path = os.path.join(filepath, ".audit_hash")
            if os.path.exists(hash_path):
                cli.log(f"DEBUG: Cleaning up audit hash: {hash_path}")
                os.remove(hash_path)

            # 4. Clear Regression Check (Rc) and Verification Passed (Vp) flags
            task.metadata["Rc"] = ""
            task.metadata["Vp"] = False

            # Update the task file
            cli._atomic_write(filepath, task)


class PatchMigrationHook(PipelineHook):
    """Ensures patches are migrated from REVIEW to STAGING."""

    def execute(self, cli, task, current_state, new_status, filepath):
        if current_state == "REVIEW" and new_status == "STAGING":
            task_folder_name = os.path.basename(filepath)
            src_patches_dir = os.path.join(
                cli.tasks_path, "review", task_folder_name, "patches"
            )
            dst_patches_dir = os.path.join(
                cli.tasks_path, "staging", task_folder_name, "patches"
            )

            if os.path.exists(src_patches_dir):
                cli.log(
                    f"DEBUG: Migrating patches from {src_patches_dir} to {dst_patches_dir}"
                )
                os.makedirs(dst_patches_dir, exist_ok=True)
                for item in os.listdir(src_patches_dir):
                    shutil.copy2(
                        os.path.join(src_patches_dir, item),
                        os.path.join(dst_patches_dir, item),
                    )
            else:
                cli.log(f"DEBUG: No patches found in {src_patches_dir} to migrate.")


class VerifyArtifactsHook(PipelineHook):
    """Proactively verifies that artifacts tracked in metadata exist on disk."""

    def execute(self, cli, task, current_state, new_status, filepath):
        if new_status in ["STAGING", "DONE"]:
            patch_files = task.metadata.get("PatchFiles", [])
            task_id = task.metadata.get("Id")

            # Check if all patches exist
            missing_patches = False
            for patch_info in patch_files:
                if not os.path.exists(patch_info.get("patch_path", "")):
                    missing_patches = True
                    break

            if missing_patches:
                cli.log(
                    f"DEBUG: Artifacts missing for task {task_id}. Re-generating patches."
                )
                from .audit import generate_file_patches

                _, branch = parse_filename(os.path.basename(filepath))

                # Regenerate all patches
                new_patches = generate_file_patches(cli, str(task_id), filepath, branch)

                # Update task metadata
                task.metadata["PatchFiles"] = new_patches
                cli._atomic_write(filepath, task)
                cli.log("DEBUG: Artifacts re-generated successfully.")


class BranchExistsHook(PipelineHook):
    """Checks if the task branch exists; if not, moves back to PROGRESSING."""

    def execute(self, cli, task, current_state, new_status, filepath):
        _, branch = parse_filename(os.path.basename(filepath))
        if not branch:
            return

        res = cli.git.run(["rev-parse", "--verify", branch], check=False)
        if res.returncode != 0:
            cli.log(f"Branch {branch} missing. Auto-demoting to PROGRESSING.")

            # 1. Trigger cleanup
            cleanup = CleanupReviewArtifactsHook()
            cleanup.execute(cli, task, new_status, "PROGRESSING", filepath)

            # 2. Move to PROGRESSING
            cli.move(task.metadata.get("Id"), "PROGRESSING")

            # 3. Raise error to inform user
            cli.error("BRANCH_MISSING_AUTO_DEMOTED", branch=branch)


class DoneAtHook(PipelineHook):
    """Records the timestamp when a task reaches DONE state."""

    def execute(self, cli, task, current_state, new_status, filepath):
        if new_status == "DONE" and not task.metadata.get("DoneAt"):
            task.metadata["DoneAt"] = datetime.now().timestamp()
            cli._atomic_write(filepath, task)


class AutoArchiveHook(PipelineHook):
    """Automatically moves a task from DONE to ARCHIVED after a 7-day grace period."""

    def execute(self, cli, task, current_state, new_status, filepath):
        if new_status == "DONE":
            done_at = task.metadata.get("DoneAt")
            if not done_at:
                return

            elapsed = datetime.now().timestamp() - done_at
            grace_period = 7 * 24 * 60 * 60  # 7 days in seconds

            if elapsed >= grace_period:
                cli.log(
                    f"Grace period expired for task {task.metadata.get('Id')}. Archiving..."
                )
                cli.move(task.metadata.get("Id"), "ARCHIVED")
