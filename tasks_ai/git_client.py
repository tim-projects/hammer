import subprocess
import os
from typing import Optional, List
from .constants import STATE_FOLDERS


class GitClient:
    """
    Service for handling all git operations.
    Aware of worktree boundaries through ProjectContext.
    """

    def __init__(self, context, logger=None):
        self.context = context
        self.logger = logger

    def log(self, message: str):
        if self.logger:
            self.logger.log(message)

    def run(
        self,
        args: List[str],
        cwd: Optional[str] = None,
        capture: bool = True,
        check: bool = False,
    ) -> subprocess.CompletedProcess:
        """Run a git command."""
        cwd = cwd or self.context.repo_root
        env = os.environ.copy()
        env["HAMMER_INTERNAL_CALL"] = "1"
        result = subprocess.run(
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

    def _handle_command_logging(self, args: List[str]):
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
            self.log(f"Git: Added worktree at '{args[args.index('add') + 1]}'")

    def get_current_branch(self):
        result = self.run(["rev-parse", "--abbrev-ref", "HEAD"])
        return result.stdout.strip()

    def get_default_branch(self):
        # Fallback to 'main' if origin/HEAD cannot be determined
        result = self.run(["symbolic-ref", "refs/remotes/origin/HEAD"])
        if result.returncode == 0:
            return result.stdout.strip().replace("refs/remotes/origin/", "")
        return "main"

    def is_merged(self, branch: str, target: str = "main") -> bool:
        # 1. Proactively refresh all remote references to avoid stale state
        self.run(["fetch", "--all"])

        # 2. Check if the branch exists locally (or as a remote tracking branch)
        res = self.run(["rev-parse", "--verify", branch])
        if res.returncode != 0:
            # Maybe it's a remote branch name, try searching for origin/branch
            res = self.run(["rev-parse", "--verify", f"origin/{branch}"])
            if res.returncode != 0:
                return False

        # 3. Check ancestry against target's remote tracking branch
        target_ref = f"origin/{target}"

        # Verify target ref exists
        if self.run(["rev-parse", "--verify", target_ref]).returncode != 0:
            target_ref = target # fallback to local if remote missing

        res = self.run(["merge-base", "--is-ancestor", branch, target_ref])
        return res.returncode == 0

    def check_main_divergence(self):
        """Check if local main is out of sync with origin/main."""
        self.run(["fetch", "origin"])
        local_res = self.run(["rev-parse", "main"])
        remote_res = self.run(["rev-parse", "origin/main"])
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
        except Exception:
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
        tasks_path = self.context.tasks_path
        if not os.path.exists(tasks_path):
            msg = "Tasks not initialized."
            if fatal and self.logger:
                self.logger.error(msg)
            return None

        remotes = self.run(["remote", "-v"], cwd=tasks_path)
        if not remotes.stdout.strip():
            self.log("No remote configured - skipping push (local-only mode)")
            return {"branch": branch, "remote": None}

        current = self.run(
            ["rev-parse", "--abbrev-ref", "HEAD"], cwd=tasks_path
        ).stdout.strip()
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
