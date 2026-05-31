import os
from .hooks import PipelineHook
from .constants import CURRENT_TASK_FILENAME
from .models import Task
from .utils import parse_filename

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
    """Runs linting and tests when exiting PROGRESSING or TESTING."""
    def execute(self, cli, task, current_state, new_status, filepath):
        if current_state in ["PROGRESSING", "TESTING"]:
            cli.console("validate", "pre-transition", f"{current_state} -> {new_status}")
            cli._run_validation()
            cli._run_tests()

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
            cli.console("gate", "review", "entered")

class BranchCheckHook(PipelineHook):
    """Handles branch restoration and remote push verification."""
    def execute(self, cli, task, current_state, new_status, filepath):
        _, branch = parse_filename(os.path.basename(filepath))
        has_origin = cli._run_git(["remote", "get-url", "origin"]).returncode == 0

        # Restoration check
        if new_status == "PROGRESSING":
            branch_sha_res = cli._run_git(["rev-parse", branch])
            branch_sha = branch_sha_res.stdout.strip() if branch_sha_res.returncode == 0 else ""
            if not branch_sha:
                if has_origin:
                    remote_check = cli._run_git(["ls-remote", "--heads", "origin", branch])
                    if remote_check.stdout.strip():
                        cli.console("git", "restore", f"{branch} from origin")
                        cli._run_git(["checkout", "-b", branch, f"origin/{branch}"], cwd=cli.root)

        # Remote push check
        if new_status in ("REVIEW", "STAGING", "DONE", "ARCHIVED"):
            if has_origin:
                if not cli._run_git(["ls-remote", "--heads", "origin", branch]).stdout:
                    cli.error("BRANCH_NOT_PUSHED", branch=branch)

class TestingPromotionHook(PipelineHook):
    """Triggers repo promotion when entering TESTING."""
    def execute(self, cli, task, current_state, new_status, filepath):
        if new_status == "TESTING":
            from repo import cmd_promote, FLAGS
            _, branch = parse_filename(os.path.basename(filepath))
            FLAGS.update({"yes": cli.yes, "quiet": cli.quiet, "json": True, "dev": cli.dev})
            try:
                cli.console("repo", "promote", branch)
                cmd_promote(branch)
            except Exception as e:
                cli.error("AUTO_PROMOTE_FAIL", error=e)

class ReviewDiffHook(PipelineHook):
    """Generates a file-level diff patches and resets Rc when entering REVIEW."""
    def execute(self, cli, task, current_state, new_status, filepath):
        if new_status == "REVIEW":
            cli.log("DEBUG: ReviewDiffHook running")
            from .audit import generate_file_patches
            _, branch = parse_filename(os.path.basename(filepath))
            task_id = task.metadata.get("Id")
            # Get the *actual* current filepath
            current_path, _ = cli.find_task(str(task_id))
            cli.console("audit", "generate", f"patches for {current_path}")
            generate_file_patches(cli, str(task_id), current_path, branch)
            task.metadata["Rc"] = ""
            # Re-dumping to update Rc in the new location
            cli._atomic_write(current_path, task)

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
        patterns = ["*.log", "__pycache__", ".pytest_cache", ".ruff_cache", ".tasks.bak_*"]
        for pattern in patterns:
            cli.console("clean", "pattern", pattern)
            cli.git.run(["clean", "-fd", "-e", ".tasks", "-e", ".env", "--", pattern])

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
            cli.git.run(["fetch", "origin", default_branch])

            # 3. Attempt merge
            merge_res = cli.git.run(["merge", f"origin/{default_branch}"])
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
                cli.error("MAIN_BRANCH_PROTECTION", new_status=new_status, default_branch=default_branch)

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
                cli.error(f"No progress tracking file found (checked {progress_path} and {current_path}).")
                
            # Get last commit version of the file
            _, branch = parse_filename(os.path.basename(filepath))
            git_res = cli.git.run(["show", f"HEAD:{os.path.relpath(progress_file, cli.tasks_path)}"], capture=True)
            
            if git_res.returncode == 0:
                last_content = git_res.stdout.strip()
                with open(progress_file, "r") as f:
                    current_content = f.read().strip()
                
                if last_content == current_content:
                    cli.error(
                        "NO_PROGRESS_UPDATE",
                        progress_path=progress_path,
                        current_path=current_path
                    )
