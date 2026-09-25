import os
import subprocess


class ProjectContext:
    """
    Central authority for path resolution and environment detection.
    Supports standard git repositories and git worktrees.
    """

    def __init__(self, dev: bool=False, tasks_dir_override: str | None=None):
        self.dev = dev
        self.repo_root = self._get_git_root()
        self.main_repo_root = self._get_main_repo_root()
        self.is_worktree = os.path.normpath(self.repo_root) != os.path.normpath(self.main_repo_root)
        if self.dev:
            self.tasks_path = os.environ.get('HAMMER_DEV_TASKS_DIR', '/tmp/.tasks')
        elif tasks_dir_override:
            if os.path.isabs(tasks_dir_override):
                self.tasks_path = tasks_dir_override
            else:
                self.tasks_path = os.path.join(self.main_repo_root, tasks_dir_override)
        else:
            self.tasks_path = os.path.join(self.main_repo_root, '.tasks')

    def _get_git_root(self) -> str:
        """Get the top-level directory of the current git repository/worktree."""
        try:
            return subprocess.check_output(['git', 'rev-parse', '--show-toplevel'], stderr=subprocess.DEVNULL).decode().strip()
        except subprocess.CalledProcessError:
            return os.getcwd()

    def _get_main_repo_root(self) -> str:
        """Get the root directory of the main repository, even if in a worktree."""
        try:
            common_dir = subprocess.check_output(['git', 'rev-parse', '--git-common-dir'], stderr=subprocess.DEVNULL).decode().strip()
            if not os.path.isabs(common_dir):
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
        return f'ProjectContext(repo_root={self.repo_root}, main_repo_root={self.main_repo_root}, is_worktree={self.is_worktree}, tasks_path={self.tasks_path})'