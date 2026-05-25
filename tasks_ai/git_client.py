import subprocess
from typing import Optional, List

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

    def run(self, args: List[str], cwd: Optional[str] = None, capture: bool = True, check: bool = False) -> subprocess.CompletedProcess:
        """Run a git command."""
        cwd = cwd or self.context.repo_root
        result = subprocess.run(
            ["git"] + args, 
            cwd=cwd, 
            capture_output=capture, 
            text=True
        )

        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, result.args, output=result.stdout, stderr=result.stderr)

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

    def get_current_branch(self) -> str:
        res = self.run(["rev-parse", "--abbrev-ref", "HEAD"])
        return res.stdout.strip()

    def is_merged(self, branch: str, target: str = "main") -> bool:
        res = self.run(["branch", "--merged", target])
        return branch in res.stdout
