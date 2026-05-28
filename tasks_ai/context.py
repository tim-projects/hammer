import os
import subprocess
from typing import Optional

class ProjectContext:
    """
    Central authority for path resolution and environment detection.
    Supports standard git repositories and git worktrees.
    """
    def __init__(self, dev: bool = False, tasks_dir_override: Optional[str] = None):
        self.dev = dev
        self.repo_root = self._get_git_root()
        self.main_repo_root = self._get_main_repo_root()
        self.is_worktree = os.path.normpath(self.repo_root) != os.path.normpath(self.main_repo_root)
        
        # Determine the base tasks directory
        if self.dev:
             # For testing backward compatibility, we use a fixed path structure
             self.tasks_path = "/tmp/.tasks"
        elif tasks_dir_override:
            if os.path.isabs(tasks_dir_override):
                self.tasks_path = tasks_dir_override
            else:
                self.tasks_path = os.path.join(self.main_repo_root, tasks_dir_override)
        else:
            # Default to .tasks in main repo root
            self.tasks_path = os.path.join(self.main_repo_root, ".tasks")

    def _get_git_root(self) -> str:
        """Get the top-level directory of the current git repository/worktree."""
        try:
            return subprocess.check_output(
                ["git", "rev-parse", "--show-toplevel"], stderr=subprocess.DEVNULL
            ).decode().strip()
        except subprocess.CalledProcessError:
            return os.getcwd()

    def _get_main_repo_root(self) -> str:
        """Get the root directory of the main repository, even if in a worktree."""
        try:
            common_dir = subprocess.check_output(
                ["git", "rev-parse", "--git-common-dir"], stderr=subprocess.DEVNULL
            ).decode().strip()
            
            if not os.path.isabs(common_dir):
                # If relative, it's relative to the current git root's .git file/dir
                # But git rev-parse --git-common-dir usually returns absolute or relative to CWD
                # Let's ensure it's absolute.
                abs_common = os.path.abspath(common_dir)
                return os.path.dirname(abs_common)
            
            return os.path.dirname(common_dir)
        except subprocess.CalledProcessError:
            return self._get_git_root()

    def resolve_path(self, *paths: str) -> str:
        """Resolve a path relative to the main repo root."""
        return os.path.join(self.main_repo_root, *paths)

    def resolve_worktree_path(self, *paths: str) -> str:
        """Resolve a path relative to the current worktree/repo root."""
        return os.path.join(self.repo_root, *paths)

    def __repr__(self):
        return (f"ProjectContext(repo_root={self.repo_root}, "
                f"main_repo_root={self.main_repo_root}, "
                f"is_worktree={self.is_worktree}, "
                f"tasks_path={self.tasks_path})")
