import os
import shutil
from datetime import datetime

from .cli_errors import PipelineMergeConflict
from .constants import CURRENT_TASK_FILENAME, STATE_FOLDERS, load_config
from .guard_engine import GuardEngine, GuardUnavailable
from .hooks import PipelineHook
from .models import Task
from .utils import commit_task_paths, parse_filename


def get_guard_engine(cli) -> GuardEngine:
    """One engine per CLI process; cache lives in the common git dir."""
    engine = getattr(cli, "_guard_engine", None)
    if engine is None:
        engine = GuardEngine(
            repo_root=cli.context.main_repo_root,
            tasks_path=cli.tasks_path,
            dev=cli.dev,
            config=load_config(cli.tasks_path),
            cwd=cli.context.repo_root,
        )
        cli._guard_engine = engine
    return engine


def _task_branch(task, filepath):
    branch = task.metadata.get("Br", "")
    if not branch:
        _, branch = parse_filename(os.path.basename(filepath))
    return branch


class GuardGateHook(PipelineHook):
    """Blocks a transition whose task violates a guard invariant.

    Runs before the physical move, so a rejection leaves the folder in place.
    Fails closed with no escape hatch: if guard cannot verify, the transition
    is rejected. Repair belongs to `hammer doctor`; the guard only assesses.
    """

    def execute(self, cli, task, current_state, new_status, filepath):
        task_id = task.metadata.get("Id")
        branch = _task_branch(task, filepath)
        try:
            engine = get_guard_engine(cli)
        except GuardUnavailable as exc:
            # No engine could even be built (e.g. not a git repo): fail closed.
            cli.error("GUARD_UNAVAILABLE", task_id=task_id, detail=str(exc))
            return

        try:
            findings = engine.verdict(task_id, current_state, new_status, branch)
        except GuardUnavailable as exc:
            cli.error("GUARD_UNAVAILABLE", task_id=task_id, detail=str(exc))
            return

        for finding in findings:
            cli.error(
                finding["code"],
                task_id=task_id,
                detail=finding["detail"],
                branch=branch,
                to_state=new_status,
            )


class GuardRecordHook(PipelineHook):
    """Records forced bypasses. Enter hooks run even under --force, so a
    forced transition past a violation is never silent: it lands in the
    anomalies table and is surfaced by 'guard scan' and 'doctor'."""

    def execute(self, cli, task, current_state, new_status, filepath):
        if not getattr(cli, "_last_move_force", False):
            return
        task_id = task.metadata.get("Id")
        try:
            engine = get_guard_engine(cli)
            findings = engine.verdict(
                task_id, current_state, new_status, _task_branch(task, filepath)
            )
        except GuardUnavailable:
            return

        recorded = []
        for finding in findings:
            detail = (
                f"forced bypass {current_state} -> {new_status}: {finding['detail']}"
            )
            if engine.record_anomaly(finding["code"], task_id, detail):
                recorded.append(finding["code"])
        if recorded:
            cli.log(
                f"[guard] FORCED BYPASS recorded for task {task_id}: "
                f"{', '.join(sorted(set(recorded)))}. Visible in 'hammer guard scan'."
            )


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
        if current_state not in ["PROGRESSING", "TESTING"]:
            return

        cli.console("validate", "pre-transition", f"{current_state} -> {new_status}")

        # Enforce presence of essential files
        for required_file in ["criteria.md", "progress.md"]:
            if not os.path.exists(os.path.join(filepath, required_file)):
                cli.error(
                    f"WHAT: Missing {required_file} | WHY: Pipeline governance requires {required_file} to be present | HOW: Run 'touch {os.path.join(filepath, required_file)}' to create the file | CONSEQUENCE: Transition halted."
                )

        # Skip expensive rerun if validation already passed
        if task.metadata.get("Tp"):
            cli.log("DEBUG: Validation already passed; skipping rerun.")
            return

        cli.run_tool("all")

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
            return not (
                tt == "issue"
                and (
                    not t.parts.get("repro")
                    or len(str(t.parts.get("repro")).strip()) < 10
                )
            )

        if current_state == "BACKLOG" and new_status not in ("BACKLOG", "REJECTED"):  # noqa: SIM102
            if not has_complete_content(task, os.path.basename(filepath)):
                cli.error("Task lacks required content to leave BACKLOG.")

        if new_status == "PROGRESSING":  # noqa: SIM102
            if not has_complete_content(task, os.path.basename(filepath)):
                cli.error("Task lacks sufficient detail to move to PROGRESSING.")


class ResearchGateHook(PipelineHook):
    """READY -> PROGRESSING requires a recorded read-only research pass.

    The pass itself is read-only (codebase files, online search); only its
    findings are written back, via 'tasks modify --research', which stores
    the research part and sets the Rr attestation. The gate needs both: a
    bare Rr flag with no findings, or findings never attested, both mean the
    task moved to implementation without anyone looking at the code.
    """

    MIN_RESEARCH_LEN = 10

    def execute(self, cli, task, current_state, new_status, filepath):
        if new_status != "PROGRESSING":
            return

        research = str(task.parts.get("research") or "").strip()
        if task.metadata.get("Rr") and len(research) >= self.MIN_RESEARCH_LEN:
            return

        cli.error("RESEARCH_REQUIRED", task_id=task.metadata.get("Id"))


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
            task.metadata["PatchGenTime"] = datetime.now().timestamp()  # noqa: DTZ005

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


def _remote_has_branch(cli, branch):
    return bool(cli._run_git(["ls-remote", "--heads", "origin", branch]).stdout.strip())


def _push_task_branch(cli, task_id, branch):
    """Push the task branch so the remote gate passes without a manual `git push`.

    The gate itself is unchanged: a push that fails, or a remote that still has
    no ref afterwards, still halts the transition.
    """
    cwd = cli.git.worktrees.get_worktree_path(task_id)
    if not cwd or not os.path.exists(cwd):
        cwd = None
    push = cli._run_git(["push", "-u", "origin", branch], cwd=cwd, check=False)
    cli.console("git", "push", branch)
    if push.returncode != 0 or not _remote_has_branch(cli, branch):
        cli.error("BRANCH_NOT_PUSHED", branch=branch)


class WorktreeCheckHook(PipelineHook):
    """Handles worktree verification and conflict detection."""

    def execute(self, cli, task, current_state, new_status, filepath):
        if cli.dev:
            return
        task_id = str(task.metadata.get("Id", ""))
        branch = task.metadata.get("Br", "")
        if not branch:
            _, branch = parse_filename(os.path.basename(filepath))

        has_origin = cli._run_git(["remote", "get-url", "origin"]).returncode == 0

        if new_status == "PROGRESSING":  # noqa: SIM102
            if not cli.git.worktrees.has_worktree(task_id):  # noqa: SIM102
                if branch and has_origin:
                    remote_check = cli._run_git(
                        ["ls-remote", "--heads", "origin", branch]
                    )
                    if remote_check.stdout.strip():
                        cli.git.worktrees.create_task_worktree(task_id, branch)
                        cli.console("worktree", "restore", f"{branch} from origin")

        if new_status in ("REVIEW", "STAGING", "DONE", "ARCHIVED"):  # noqa: SIM102
            if has_origin:  # noqa: SIM102
                if not _remote_has_branch(cli, branch):
                    _push_task_branch(cli, task_id, branch)


class ReviewDiffHook(PipelineHook):
    """Ensures file-level diff patches are generated when entering REVIEW."""

    def execute(self, cli, task, current_state, new_status, filepath):
        if new_status == "REVIEW":
            cli.log(
                f"ReviewDiffHook triggered for task {task.metadata.get('Id')}. Ensuring patches exist."
            )
            cli.log("")
            from .audit import generate_file_patches, get_patch_snapshot

            branch = task.metadata.get("Br", "")
            if not branch:
                _, branch = parse_filename(os.path.basename(filepath))
            task_id = task.metadata.get("Id")

            cli.log(f" for task {task_id}")
            task.metadata["Reviewed"] = False
            task.metadata["Rc"] = ""
            task.metadata["PatchGenTime"] = datetime.now().timestamp()  # noqa: DTZ005
            reviews_path = os.path.join(filepath, "reviews.json")
            if os.path.exists(reviews_path):
                os.remove(reviews_path)

            patches = generate_file_patches(
                cli,
                str(task_id),
                filepath,
                branch,
                patches_dir=os.path.join(filepath, "patches"),
            )
            cli.log(f"Got {len(patches)} patches")
            task.metadata["PatchFiles"] = patches
            task.metadata["PatchSnapshot"] = get_patch_snapshot(cli, branch)
            cli._atomic_write(filepath, task)
            cli.log("ReviewDiffHook: patches verified and generated.")


class ArchivedCommitHook(PipelineHook):
    """Commits and pushes the tasks worktree when entering ARCHIVED, then removes the task worktree.

    Finalizes the task: confirms the worktree branch is merged to main before removing
    the worktree, ensuring no work is lost on archive.
    """

    def execute(self, cli, task, current_state, new_status, filepath):
        if new_status == "ARCHIVED":
            task_id = str(task.metadata.get("Id", ""))

            # The push below is only safe if the pushed state is this task's own:
            # a store-wide add would commit every other agent's pending work and
            # then propagate it to origin under this archive's message.
            old_path = os.path.join(
                cli.tasks_path,
                STATE_FOLDERS.get(current_state, current_state),
                os.path.basename(filepath),
            )
            commit_task_paths(
                cli,
                filepath,
                f"Archive [{task.metadata.get('Id')}] {task.metadata.get('Ti')}",
                old_path,
            )
            try:
                cli._push_tasks_branch("tasks", fatal=False)
            except Exception:  # noqa: BLE001, S110
                pass

            # Finalize: confirm worktree branch is merged to main before cleanup
            branch = task.metadata.get("Br", "")
            default_branch = cli.git.get_default_branch()
            if branch and not cli.git.is_merged(branch, default_branch):
                cli.error("BRANCH_NOT_MERGED", branch=branch)

            if cli.git.worktrees.has_worktree(task_id):
                cli.git.worktrees.remove_task_worktree(task_id, force=True)
                cli.console("worktree", "remove", f"task {task_id}")
            else:
                cli.console("worktree", "skip", f"no worktree for task {task_id}")


class PostMoveCommitHook(PipelineHook):
    """Store commit for a move.

    This ran before the physical move, where a store-wide 'add -f .' committed
    every agent's pending work under this move's message and left the staged copy
    plus both the old and new task paths uncommitted. move_logic now commits the
    task's old and new paths after the move, so this hook no longer touches the
    store.
    """

    def execute(self, cli, task, current_state, new_status, filepath):
        return


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


class WorktreeSyncHook(PipelineHook):
    """Ensures the task worktree is mounted and synced with main on PROGRESSING."""

    def execute(self, cli, task, current_state, new_status, filepath):
        if new_status == "PROGRESSING":
            task_id = str(task.metadata.get("Id", ""))
            branch = task.metadata.get("Br", "")
            if not branch:
                branch = task_id

            cli.console("worktree", "sync", f"{branch}")

            if not cli.git.worktrees.has_worktree(task_id):
                cli.git.worktrees.create_task_worktree(task_id, branch)

            worktree_path = cli.git.worktrees.get_worktree_path(task_id)
            if not worktree_path:
                cli.error("WORKTREE_NOT_FOUND", task_id=task_id)

            default_branch = cli.git.get_default_branch()
            if not default_branch:
                cli.console("worktree", "sync", "skipped (no main/master)")
                return

            try:
                merged_source = cli.git.sync_worktree(
                    worktree_path, default_branch, branch
                )
            except PipelineMergeConflict as e:
                cli.console("worktree", "merge", "conflict")
                cli.error(
                    "WORKTREE_MERGE_CONFLICT",
                    branch=e.branch,
                    default=e.default,
                )

            if not merged_source:
                cli.console("worktree", "sync", "skipped (no remote/default)")
                return

            cli.console("worktree", "sync", "complete")


class MainBranchProtectionHook(PipelineHook):
    """Prevents transitions if the user is working directly on the main branch or outside a task worktree."""

    def execute(self, cli, task, current_state, new_status, filepath):
        if cli.dev:
            return
        if new_status in ["PROGRESSING", "TESTING", "REVIEW", "STAGING", "DONE"]:
            current_branch = cli.git.get_current_branch()
            default_branch = cli.git.get_default_branch()

            if current_branch == default_branch:
                # Allow transitions from default branch if the task has its own branch —
                # the pipeline engine handles worktree context internally
                task_branch = task.metadata.get("Br", "")
                if not task_branch:
                    cli.error(
                        "MAIN_BRANCH_PROTECTION",
                        new_status=new_status,
                        default_branch=default_branch,
                    )

            if not cli.git.worktrees.is_in_task_worktree():
                task_id = str(task.metadata.get("Id", ""))
                branch = task.metadata.get("Br", "")
                cli.log(
                    f"WARN: Not in a task worktree for task {task_id}. "
                    f"Run 'tasks mount {task_id}' to mount worktree '{branch}'."
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
            _, _branch = parse_filename(os.path.basename(filepath))
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


class WorktreeSyncOnExitTestingHook(PipelineHook):
    """Detect and merge missing commit during exit TESTING via worktree."""

    def execute(self, cli, task, current_state, new_status, filepath):
        if current_state == "TESTING" and new_status != "TESTING":
            task_id = str(task.metadata.get("Id", ""))
            branch = task.metadata.get("Br", "")
            if not branch:
                _, branch = parse_filename(os.path.basename(filepath))

            default_branch = cli.git.get_default_branch()
            if not default_branch:
                cli.console("worktree", "check", "skipped (no main/master)")
                return
            cli.console("worktree", "check", "divergence")
            res = cli.git.run(
                ["rev-list", f"{default_branch}..{branch}", "--count"],
                cwd=cli.context.main_repo_root,
            )
            if res.stdout.strip() != "0":
                cli.console("worktree", "merge", "missing commit")
                wt_path = cli.git.worktrees.get_worktree_path(task_id)
                cwd = wt_path if wt_path and os.path.exists(wt_path) else cli.root
                cli.git.run(["merge", default_branch], cwd=cwd)


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

            reviews_path = os.path.join(filepath, "reviews.json")
            if os.path.exists(reviews_path):
                cli.log(f"DEBUG: Clearing review receipts: {reviews_path}")
                os.remove(reviews_path)

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


class WorktreeExistsHook(PipelineHook):
    """Checks if the task worktree exists; if not, moves back to PROGRESSING."""

    def execute(self, cli, task, current_state, new_status, filepath):
        task_id = str(task.metadata.get("Id", ""))
        branch = task.metadata.get("Br", "")
        if not branch:
            _, branch = parse_filename(os.path.basename(filepath))
        if not branch:
            return

        has_worktree = cli.git.worktrees.has_worktree(task_id)
        branch_exists = (
            cli.git.run(
                ["rev-parse", "--verify", branch],
                cwd=cli.context.main_repo_root,
                check=False,
            ).returncode
            == 0
        )

        if not has_worktree and not branch_exists:
            cli.log(f"Worktree {branch} missing. Auto-demoting to PROGRESSING.")

            cleanup = CleanupReviewArtifactsHook()
            cleanup.execute(cli, task, new_status, "PROGRESSING", filepath)

            cli.move(task.metadata.get("Id"), "PROGRESSING")

            cli.error("WORKTREE_MISSING_AUTO_DEMOTED", branch=branch)


class DoneAtHook(PipelineHook):
    """Records the timestamp when a task reaches DONE state."""

    def execute(self, cli, task, current_state, new_status, filepath):
        if new_status == "DONE" and not task.metadata.get("DoneAt"):
            task.metadata["DoneAt"] = datetime.now().timestamp()  # noqa: DTZ005
            cli._atomic_write(filepath, task)


class AutoArchiveHook(PipelineHook):
    """Automatically moves a task from DONE to ARCHIVED after a 7-day grace period."""

    def execute(self, cli, task, current_state, new_status, filepath):
        if new_status == "DONE":
            done_at = task.metadata.get("DoneAt")
            if not done_at:
                return

            elapsed = datetime.now().timestamp() - done_at  # noqa: DTZ005
            grace_period = 7 * 24 * 60 * 60  # 7 days in seconds

            if elapsed >= grace_period:
                cli.log(
                    f"Grace period expired for task {task.metadata.get('Id')}. Archiving..."
                )
                cli.move(task.metadata.get("Id"), "ARCHIVED")
