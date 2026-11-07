import os
import subprocess

from .constants import STATE_FOLDERS


class GitService:
    """
    Service for handling all git operations.
    Aware of worktree boundaries through ProjectContext.
    """

    def __init__(self, context, logger=None):
        self.context = context
        self.logger = logger
        self._worktree_manager = None

    @property
    def worktrees(self):
        if self._worktree_manager is None:
            from .worktree_manager import WorktreeManager

            self._worktree_manager = WorktreeManager(
                self.context, self, logger=self.logger
            )
        return self._worktree_manager

    def log(self, message: str):
        if self.logger:
            self.logger.log(message)

    def run(
        self,
        args: list[str],
        cwd: str | None = None,
        capture: bool = True,
        check: bool = False,
    ) -> subprocess.CompletedProcess:
        """Run a git command."""
        cwd = cwd or self.context.repo_root
        env = os.environ.copy()
        env["HAMMER_INTERNAL_CALL"] = (
            "1"  # exemption for hammer's own merge promotions (pre-merge-commit hook)
        )
        result = subprocess.run(  # noqa: PLW1510
            ["git"] + args, cwd=cwd, capture_output=capture, text=True, env=env
        )

        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                result.args,
                output=result.stdout,
                stderr=result.stderr,
            )

        if result.returncode == 0:
            self._handle_command_logging(args)

        return result

    def _handle_command_logging(self, args: list[str]):
        """Standardized logging for common git operations."""
        if not args:
            return
        cmd = args[0]
        if cmd == "checkout":
            branch = args[-1]
            if "-b" in args:
                self.log(f"Git: Created and switched to branch '{branch}'")
            else:
                self.log(f"Git: Switched to branch '{branch}'")
        elif cmd == "commit":
            msg = ""
            if "-m" in args:
                idx = args.index("-m")
                msg = f": {args[idx + 1]}"
            self.log(f"Git: Committed changes{msg}")
        elif cmd == "push":
            remote = args[1] if len(args) > 1 else ""
            branch = args[2] if len(args) > 2 else ""
            self.log(f"Git: Pushed {branch} to {remote}")
        elif cmd == "branch" and ("-d" in args or "-D" in args):
            branch = args[-1]
            self.log(f"Git: Deleted branch '{branch}'")
        elif cmd == "merge":
            self.log(f"Git: Merged '{args[-1]}'")
        elif cmd == "worktree" and "add" in args:
            # Handles both `add <path> <branch>` and `add -b <branch> <path>`
            self.log(f"Git: Added worktree at '{args[-1]}'")
        elif cmd == "worktree" and ("remove" in args or "prune" in args):
            action = "Removed" if "remove" in args else "Pruned"
            target = args[-1]
            self.log(f"Git: {action} worktree at '{target}'")

    def get_current_branch(self):
        result = self.run(["rev-parse", "--abbrev-ref", "HEAD"])
        return result.stdout.strip()

    def get_default_branch(self) -> str | None:
        """The repo's default branch: origin/HEAD, else the first existing of
        main/master. None when neither exists - callers must handle that
        rather than assume a branch git does not have."""
        # Try origin/HEAD first
        result = self.run(["symbolic-ref", "refs/remotes/origin/HEAD"])
        if result.returncode == 0:
            return result.stdout.strip().replace("refs/remotes/origin/", "")
        # Try common local branches
        for branch in ["main", "master"]:
            res = self.run(["rev-parse", "--verify", branch])
            if res.returncode == 0:
                return branch
        return None

    def is_merged(
        self, branch: str, target: str | None = None, cwd: str | None = None
    ) -> bool:
        cwd = cwd or self.context.main_repo_root
        if target is None:
            target = self.get_default_branch()
            if not target:
                # Without main/master there is nothing a branch could be
                # merged into, so "merged" cannot be proven.
                return False
        if self.context.dev:
            # A dev repo never pushes, so its origin is only a snapshot of the
            # repo it was cloned from: local merges are the only truth here.
            target_ref = target
        else:
            # 1. Proactively refresh all remote references to avoid stale state
            self.run(["fetch", "--all"], cwd=cwd)

        # 2. Check if the branch exists locally (or as a remote tracking branch)
        res = self.run(["rev-parse", "--verify", branch], cwd=cwd)
        if res.returncode != 0:
            # Maybe it's a remote branch name, try searching for origin/branch
            res = self.run(["rev-parse", "--verify", f"origin/{branch}"], cwd=cwd)
            if res.returncode != 0:
                return False

        # 3. Check ancestry against target's remote tracking branch
        if not self.context.dev:
            target_ref = f"origin/{target}"

            # Verify target ref exists
            if self.run(["rev-parse", "--verify", target_ref], cwd=cwd).returncode != 0:
                target_ref = target  # fallback to local if remote missing

        res = self.run(
            ["merge-base", "--is-ancestor", branch, target_ref],
            cwd=cwd,
        )
        return res.returncode == 0

    def check_main_divergence(self):
        """Check if the default branch is out of sync with its remote."""
        default = self.get_default_branch()
        if not default:
            return True, None, None
        self.run(["fetch", "origin"])
        local_res = self.run(["rev-parse", default])
        remote_res = self.run(["rev-parse", f"origin/{default}"])
        if local_res.returncode == 0 and remote_res.returncode == 0:
            local = local_res.stdout.strip()
            remote = remote_res.stdout.strip()
            if local != remote:
                return False, local, remote
        return True, None, None

    def generate_review_diff(self, task_path: str, branch: str) -> str:
        """Generate a unified diff patch for the task branch against main including unstaged changes."""
        tasks_path = self.context.tasks_path
        review_dir = os.path.join(tasks_path, STATE_FOLDERS["REVIEW"])
        task_id = os.path.basename(task_path)
        diff_path = os.path.join(review_dir, f"{task_id}.patch")

        os.makedirs(review_dir, exist_ok=True)

        self.log(
            f"[DEBUG] Generating review diff: task_id={task_id}, branch='{branch}'"
        )

        default_branch = self.get_default_branch()
        main_sha = None
        try:
            main_sha = self.run(["rev-parse", default_branch]).stdout.strip()
        except Exception:  # noqa: BLE001
            main_sha = None

        diff_content = ""

        if main_sha:
            result = self.run(["diff", f"{default_branch}...{branch}"])
            if result.returncode == 0 and result.stdout.strip():
                diff_content += result.stdout

        # Get unstaged working tree changes
        result = self.run(["diff", "--patch"])
        if result.returncode == 0 and result.stdout:
            if diff_content and not diff_content.endswith("\n"):
                diff_content += "\n"
            diff_content += result.stdout

        # Get staged changes
        result = self.run(["diff", "--cached", "--patch"])
        if result.returncode == 0 and result.stdout:
            if diff_content and not diff_content.endswith("\n"):
                diff_content += "\n"
            diff_content += f"# Staged changes:\n{result.stdout}"

        with open(diff_path, "w", encoding="utf-8") as f:
            f.write(diff_content or "# No changes detected\n")

        self.log(f"Regression diff generated at {diff_path}")
        return diff_path

    def push_tasks_branch(self, branch="tasks", fatal=True):
        """Internal: push current .tasks worktree branch to remote."""
        if self.context.dev:
            # A dev store's remote is the real repo: pushing from it would move
            # real refs, which is exactly what dev mode must never do.
            self.log("Dev mode: push to remote skipped (throwaway store).")
            return {"branch": branch, "remote": None}
        tasks_path = self.context.tasks_path
        if not os.path.exists(tasks_path):
            msg = "Tasks not initialized."
            if fatal and self.logger:
                self.logger.error(msg)
            return None

        remotes = self.run(["remote", "-v"], cwd=tasks_path)
        self.log(f"DEBUG: Remotes stdout in {tasks_path}: '{remotes.stdout}'")
        if not remotes.stdout.strip():
            parent_remote = self.run(
                ["remote", "get-url", "origin"], cwd=self.context.repo_root
            )
            if parent_remote.returncode == 0 and parent_remote.stdout.strip():
                remote_url = parent_remote.stdout.strip()
                self.log(
                    f"DEBUG: Adding parent remote '{remote_url}' to .tasks for sync"
                )
                self.run(["remote", "add", "origin", remote_url], cwd=tasks_path)
            else:
                self.log("No remote configured - skipping push (local-only mode)")
                return {"branch": branch, "remote": None}

        self.run(["fetch", "origin"], cwd=tasks_path)
        current = self.run(
            ["rev-parse", "--abbrev-ref", "HEAD"], cwd=tasks_path
        ).stdout.strip()
        merge_base = self.run(
            ["merge-base", current, f"origin/{branch}"], cwd=tasks_path
        )
        if merge_base.returncode == 0:
            head = self.run(["rev-parse", current], cwd=tasks_path).stdout.strip()
            remote_head = self.run(
                ["rev-parse", f"origin/{branch}"], cwd=tasks_path
            ).stdout.strip()
            if head != remote_head:
                self.run(
                    [
                        "merge",
                        f"origin/{branch}",
                        "-m",
                        "sync: merge remote tasks branch",
                    ],
                    cwd=tasks_path,
                )

        push_result = self.run(
            ["push", "-u", "origin", f"{current}:refs/heads/{branch}"], cwd=tasks_path
        )

        if push_result.returncode != 0:
            msg = f"Failed to push .tasks worktree to remote: {push_result.stderr}"
            if fatal and self.logger:
                self.logger.error(msg)
            else:
                self.log(f"Warning: {msg}")
            return None

        self.log(f"Pushed .tasks ({current}) to origin/{branch}")
        return {"branch": branch, "remote": "origin", "from_branch": current}

    def get_next_logical_state(self, current_state: str) -> str | None:
        """Map a task's current state to its next logical promotion target."""
        from .constants import PIPELINE_STAGES

        if current_state not in PIPELINE_STAGES:
            return None
        idx = PIPELINE_STAGES.index(current_state)
        if idx + 1 < len(PIPELINE_STAGES):
            return PIPELINE_STAGES[idx + 1]
        return None

    def sync_pipeline(self, yes=False):
        """Sync all pipeline branches: testing -> staging -> default branch."""
        self.log("Syncing pipeline branches...")
        target = self.get_default_branch()
        if not target:
            self.log("Skipping pipeline sync: no default branch (main/master) exists.")
            return
        # logic from repo sync
        self.merge_branches("testing", "staging", yes=yes)
        self.merge_branches("staging", target, yes=yes)

    def merge_branches(
        self, src: str, target: str, message: str | None = None, yes=False
    ):
        """Robustly merge one branch into another with pull/push orchestration.

        All operations run from the main repo root since pipeline branches
        (main, staging, testing) live there. Task worktree branches are
        backed by branches in the same object database.
        """
        self.log(f"Merging {src} -> {target}...")

        repo_root = self.context.main_repo_root

        # 1. Ensure src and target exist
        if not self.branch_exists(src, repo_root) or not self.branch_exists(
            target, repo_root
        ):
            self.log(f"Skipping merge: {src} or {target} does not exist.")
            return

        # 2. Checkout target
        self.run(["checkout", target], cwd=repo_root)

        # 3. Pull latest
        self.run(["pull", "origin", target], cwd=repo_root, check=False)

        # 4. Merge
        msg = message or f"merge: {src} into {target}"
        merge_res = self.run(["merge", "--no-ff", src, "-m", msg], cwd=repo_root)

        if merge_res.returncode != 0:
            raise RuntimeError(f"Merge conflict {src} -> {target}. Resolve manually.")

        # 5. Push if confirmed (never in dev: the dev repo's origin is the real repo)
        if yes and not self.context.dev:
            self.run(["push", "origin", target], cwd=repo_root)

    def branch_exists(self, name: str, cwd: str | None = None) -> bool:
        return (
            self.run(["rev-parse", "--verify", name], cwd=cwd, check=False).returncode
            == 0
        )

    def promote_task(
        self,
        task,
        target_state: str,
        current_state: str | None = None,
        yes: bool = False,
    ):
        """Perform the git merges associated with a pipeline promotion.

        Works with task worktrees: the task's branch (backing its worktree)
        is merged through the pipeline branches in the main repo.
        """
        branch = task.metadata.get("Br", "")
        if not branch:
            return

        task_id = task.metadata.get("Id", "unknown")
        repo_root = self.context.main_repo_root

        # 0. Auto-commit any uncommitted changes in the worktree before transition
        wt_path = self.worktrees.get_worktree_path(str(task_id))
        commit_cwd = wt_path if wt_path and os.path.exists(wt_path) else repo_root
        status_res = self.run(["status", "--porcelain"], cwd=commit_cwd)
        if status_res.stdout.strip():
            self.log(
                f"Git: Detected uncommitted changes. Auto-committing before {target_state}..."
            )
            self.run(["add", "."], cwd=commit_cwd)
            self.run(
                [
                    "commit",
                    "-m",
                    f"[{task_id}] Auto-commit before {target_state} transition",
                ],
                cwd=commit_cwd,
            )

        # PROMOTION: Merge worktree branch through pipeline branches
        pipeline_map = {
            "TESTING": "testing",
            "STAGING": "staging",
            "DONE": self.get_default_branch(),
        }
        target_git_branch = pipeline_map.get(target_state)
        if not target_git_branch:
            if target_state == "DONE":
                self.log("Skipping merge: no default branch (main/master) exists.")
            return

        # Special case source branches
        src_branch = branch
        if target_state == "STAGING":
            src_branch = "testing"
        elif target_state == "DONE":
            src_branch = "staging"

        # Check if src_branch exists locally
        if not self.branch_exists(src_branch, repo_root):
            if src_branch in ["testing", "staging"]:
                self.log(
                    f"Pipeline branch {src_branch} does not exist locally. Merging {branch} directly into {target_git_branch}."
                )
                src_branch = branch
            else:
                self.log(f"Branch {src_branch} does not exist locally. Skipping merge.")
                return

        self.log(f"Performing pipeline promotion: {src_branch} -> {target_git_branch}")

        # Use unified merge logic
        self.merge_branches(
            src_branch,
            target_git_branch,
            message=f"[{task_id}] merge: {src_branch} into {target_git_branch}",
            yes=yes or target_state == "DONE",
        )

        # Auto-save .tasks after successful merge to main
        if target_state == "DONE":
            self.log("Auto-saving .tasks to remote tasks branch after main merge...")
            save_result = self.push_tasks_branch(branch="tasks", fatal=False)
            if save_result and save_result.get("remote"):
                self.log("✅ .tasks auto-saved to origin/tasks")
            else:
                self.log("⚠️  Failed to auto-save .tasks to origin/tasks")

        # Worktree is NOT removed on DONE - it persists for potential demotion
        # back to earlier states. Removal happens on ARCHIVED (see ArchivedCommitHook).

    def demote_task(
        self,
        task,
        target_state: str,
        current_state: str | None = None,
        force: bool = False,
    ):
        """Sync higher branches back into task worktree branch during demotion."""
        branch = task.metadata.get("Br", "")
        if not branch:
            return

        task_id = task.metadata.get("Id", "unknown")
        repo_root = self.context.main_repo_root

        self.log(
            f"Demoting task {task_id}. Syncing higher branches back to worktree branch {branch}..."
        )

        default_branch = self.get_default_branch()
        higher = [default_branch] if default_branch else []
        branches_to_sync = []
        if target_state == "PROGRESSING":
            branches_to_sync = higher + ["staging", "testing"]
        elif target_state in ["TESTING", "REVIEW"]:
            branches_to_sync = higher + ["staging"]

        if not self.branch_exists(branch, repo_root):
            if target_state == "REJECTED" or force:
                self.log(
                    f"Branch {branch} does not exist locally. Skipping demotion sync for {target_state} transition."
                )
                return
            else:
                raise RuntimeError(f"Branch {branch} does not exist locally.")

        # Sync into the worktree (if it exists) or the branch directly
        wt_path = self.worktrees.get_worktree_path(str(task_id))
        if wt_path and os.path.exists(wt_path):
            self.run(["checkout", branch], cwd=wt_path)
            for b in branches_to_sync:
                if self.branch_exists(b, repo_root):
                    self.log(f"Git: Syncing {b} -> {branch} (demotion)")
                    self.run(
                        ["merge", b, "-m", f"Sync: {b} -> {branch} (demotion)"],
                        cwd=wt_path,
                    )
        else:
            self.run(["checkout", branch], cwd=repo_root)
            for b in branches_to_sync:
                if self.branch_exists(b, repo_root):
                    self.log(f"Git: Syncing {b} -> {branch} (demotion)")
                    self.run(
                        ["merge", b, "-m", f"Sync: {b} -> {branch} (demotion)"],
                        cwd=repo_root,
                    )
